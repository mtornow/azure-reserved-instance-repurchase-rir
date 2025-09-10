"""
Module for calculating reservation order details using Azure Reserved Instance Calculate API.
This module generates the reservation order ID needed for the purchase API call.
"""

import json
import pandas as pd
from generate_json_payload import read_input_file

API_VERSION = "2022-11-01"
CALCULATE_API_URL = f"https://management.azure.com/providers/Microsoft.Capacity/calculatePrice?api-version={API_VERSION}"


def build_calculate_payload(row):
    """Build the payload for the Calculate API from a CSV row"""
    payload = {
        "sku": {"name": row["SKU-name"]},
        "location": row["azure region"],
        "properties": {
            "reservedResourceType": row["reservedResourceType"],
            "billingScopeId": f"/subscriptions/{row['subscription']}",
            "term": row["term"],
            "billingPlan": row["billingPlan"],
            "quantity": int(row["quantity"]),
            "displayName": row["displayName"],
            "appliedScopes": None if pd.isna(row["appliedScopes"]) or row["appliedScopes"] == '' else row["appliedScopes"],
            "appliedScopeType": row["appliedScopeType"],
            "reservedResourceProperties": {
                "instanceFlexibility": row["InstanceFlexibility"]
            }
            # Note: 'renew' is not included in Calculate API, only in Purchase API
        }
    }
    return payload


def calculate_reservation_order(file_path, access_token=None, save_to_csv=True):
    """
    Calculate reservation order details for all rows in the input file.
    Returns a list of calculation responses including reservation order IDs.
    
    Args:
        file_path: Path to the input CSV file
        access_token: Azure access token for API authentication (required for real API calls)
        save_to_csv: Whether to save the results back to CSV with new column
    
    Returns:
        List of dictionaries containing calculation results
    
    Raises:
        ValueError: If access_token is not provided
        requests.HTTPError: If API call fails
    """
    if not access_token:
        raise ValueError("access_token is required for Azure API calls. Please provide a valid Azure access token.")
    
    df = read_input_file(file_path)
    calculation_results = []
    reservation_order_ids = []
    price_responses = []
    
    for index, row in df.iterrows():
        calculate_payload = build_calculate_payload(row)
        
        try:
            import requests
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            print(f"Making API call for row {index + 1}: {row['SKU-name']} in {row['azure region']}")
            response = requests.post(CALCULATE_API_URL, 
                                   headers=headers, 
                                   json=calculate_payload)
            
            if response.status_code == 200:
                result = response.json()
            else:
                error_msg = f"API call failed with status {response.status_code}"
                if response.content:
                    try:
                        error_detail = response.json()
                        error_msg += f": {error_detail}"
                    except:
                        error_msg += f": {response.text}"
                raise requests.HTTPError(error_msg)
                
        except ImportError:
            raise ImportError("requests library is required for API calls. Please install it with: pip install requests")
        except Exception as e:
            raise Exception(f"Failed to calculate reservation for row {index + 1} ({row['SKU-name']}): {str(e)}")
        
        reservation_order_id = result.get('properties', {}).get('reservationOrderId')
        if not reservation_order_id:
            raise ValueError(f"No reservation order ID returned in API response for row {index + 1}")
            
        reservation_order_ids.append(reservation_order_id)
        
        # Extract amount and currency for price response
        billing_total = result.get('properties', {}).get('billingCurrencyTotal', {})
        amount = billing_total.get('amount', 0)
        currency = billing_total.get('currencyCode', 'USD')
        price_summary = f"{amount} {currency}"
        price_responses.append(price_summary)
        
        calculation_results.append({
            'input_row': row,
            'calculate_request': calculate_payload,
            'calculate_response': result,
            'reservation_order_id': reservation_order_id
        })
    
    # Save results back to CSV if requested
    if save_to_csv:
        save_results_to_csv(df, reservation_order_ids, price_responses, file_path)
    return calculation_results


def save_results_to_csv(df, reservation_order_ids, price_responses, original_file_path):
    """Save the DataFrame with new Reservation Order ID and price summary columns to CSV"""
    import os
    # Add the new columns
    df['ReservationOrderID'] = reservation_order_ids
    df['Price'] = price_responses
    df['Purchased Confirmed'] = ''  # Add empty "Purchased Confirmed" column
    # Create output filename
    directory = os.path.dirname(original_file_path)
    filename = os.path.basename(original_file_path)
    name, ext = os.path.splitext(filename)
    output_filename = f"{name}_with_order_ids{ext}"
    output_path = os.path.join(directory, output_filename)
    # Save to CSV with semicolon separator (matching input format)
    df.to_csv(output_path, sep=';', index=False)
    print(f"Results saved to: {output_path}")
    print(f"Added ReservationOrderID, Price, and 'Purchased Confirmed' columns with {len(reservation_order_ids)} order ID(s)")
    return output_path


def print_calculate_results(calculation_results):
    """Print the calculate API results in a readable format"""
    for i, result in enumerate(calculation_results, 1):
        print(f"=== Calculation Result {i} ===")
        print(f"POST {CALCULATE_API_URL}")
        print(json.dumps(result['calculate_request'], indent=2))
        print(f"\nResponse (Status: 200):")
        print(json.dumps(result['calculate_response'], indent=2))
        print(f"\nReservation Order ID: {result['reservation_order_id']}")
        print("-" * 50)
        print()


if __name__ == "__main__":
    # Test the module
    import os
    
    INPUT_DIR = "input_file"
    INPUT_FILE = "example_RI_purchase.csv"
    file_path = os.path.join(INPUT_DIR, INPUT_FILE)
    
    if os.path.exists(file_path):
        results = calculate_reservation_order(file_path)
        print_calculate_results(results)
    else:
        print(f"Input file not found: {file_path}")
