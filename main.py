import json
import os
import pandas as pd
from calculate_reservation_order import calculate_reservation_order
from generate_json_payload import generate_api_payloads_with_order_ids

INPUT_DIR = "input_file"
DEFAULT_INPUT_FILE = "example_RI_purchase.csv"

API_VERSION = "2022-11-01"


def get_azure_access_token():
    """Get Azure access token using Azure CLI or Azure SDK"""
    import subprocess
    import shutil
    import platform
    
    try:
        # Try to find Azure CLI in PATH first (works cross-platform)
        az_command = shutil.which('az')
        
        if not az_command:
            # If not in PATH, try platform-specific common locations
            system = platform.system()
            possible_paths = []
            
            if system == "Windows":
                possible_paths = [
                    'C:\\Program Files\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd',
                    'C:\\Program Files (x86)\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd'
                ]
            elif system == "Darwin":  # macOS
                possible_paths = [
                    '/usr/local/bin/az',
                    '/opt/homebrew/bin/az'
                ]
            elif system == "Linux":
                possible_paths = [
                    '/usr/bin/az',
                    '/usr/local/bin/az',
                    '/opt/az/bin/az'
                ]
            
            # Find the first existing path
            for path in possible_paths:
                if shutil.which(path):
                    az_command = path
                    break
        
        if az_command:
            try:
                # Add Azure CLI directory to PATH for current process
                import os
                az_dir = os.path.dirname(az_command)
                current_path = os.environ.get('PATH', '')
                if az_dir not in current_path:
                    os.environ['PATH'] = f"{az_dir};{current_path}"
                
                result = subprocess.run([az_command, 'account', 'get-access-token', 
                                       '--resource=https://management.azure.com/', 
                                       '--query=accessToken', '--output=tsv'], 
                                      capture_output=True, text=True, check=True)
                return result.stdout.strip()
            except subprocess.CalledProcessError as e:
                raise Exception(f"Azure CLI command failed: {e.stderr}")
        
        # If Azure CLI not found, try using Azure SDK
        try:
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
            token = credential.get_token("https://management.azure.com/.default")
            return token.token
        except ImportError:
            raise ImportError("Azure CLI not found and Azure SDK not available. Please install Azure CLI or run: pip install azure-identity")
        except Exception as e:
            raise Exception(f"Failed to get Azure access token using Azure SDK. Please run 'az login --use-device-code' first. Error: {e}")
            
    except Exception as e:
        raise Exception(f"Failed to get Azure access token: {e}")


def display_purchase_trigger_summary(calculation_results):
    """Display purchase trigger fields for user confirmation"""
    print("Step 2: Review Purchase Trigger Fields")
    print("=" * 60)
    print("Please review the following purchase trigger settings for each reservation:")
    print()
    
    for i, result in enumerate(calculation_results, 1):
        row = result['input_row']  # Get the original CSV row data
        
        # Handle NaN values for Purchase Trigger
        purchase_trigger = row.get('Purchase Trigger', 'Not Set')
        if pd.isna(purchase_trigger) or str(purchase_trigger).lower() == 'nan':
            purchase_trigger = 'Not Set'
        
        print(f"Reservation {i}:")
        
        # Highlight Purchase Trigger status prominently
        if purchase_trigger == 'Not Set':
            print(f"  ⚠️  Purchase Trigger: '{purchase_trigger}' - PURCHASES WILL BE SKIPPED")
        else:
            print(f"  ✅ Purchase Trigger: '{purchase_trigger}' - PURCHASES ENABLED")
            
        print(f"  - SKU: {row.get('SKU-name', 'N/A')}")
        print(f"  - Region: {row.get('azure region', 'N/A')}")
        print(f"  - Quantity: {row.get('quantity', 'N/A')}")
        print(f"  - Term: {row.get('term', 'N/A')}")
        print(f"  - Billing Plan: {row.get('billingPlan', 'N/A')}")
        print(f"  - Display Name: {row.get('displayName', 'N/A')}")
        print(f"  - Reservation Order ID: {result.get('reservation_order_id', 'N/A')}")
        
        # Extract price from the calculate response
        billing_total = result.get('calculate_response', {}).get('properties', {}).get('billingCurrencyTotal', {})
        amount = billing_total.get('amount', 'N/A')
        currency = billing_total.get('currencyCode', 'USD')
        price_display = f"{amount} {currency}" if amount != 'N/A' else 'N/A'
        print(f"  - Estimated Price: {price_display}")
        print()
    
    return True


def get_user_confirmation():
    """Get user confirmation to proceed with purchase payload generation"""
    print("IMPORTANT: Please ensure that:")
    print("1. Purchase Trigger fields are set to 'yes' for rows you want to purchase")
    print("2. All reservation details (SKU, region, quantity, etc.) are accurate")
    print("3. You have reviewed the estimated prices")
    print()
    print("⚠️  NOTE: Only rows with Purchase Trigger = 'yes' will generate purchase payloads")
    print()
    
    while True:
        confirmation = input("Do you want to proceed with generating purchase API payloads? (yes/no): ").strip().lower()
        if confirmation in ['yes', 'y']:
            return True
        elif confirmation in ['no', 'n']:
            return False
        else:
            print("Please enter 'yes' or 'no'")


def get_api_execution_confirmation():
    """Get user confirmation to execute actual Azure API calls"""
    print()
    print("Step 4: Execute Azure Purchase API Calls (OPTIONAL)")
    print("=" * 60)
    print("⚠️  WARNING: This will make ACTUAL Azure API calls to purchase reserved instances!")
    print("💰 This will result in REAL charges to your Azure subscription!")
    print()
    print("Prerequisites:")
    print("1. You must be authenticated with Azure (run 'az login --use-device-code' first)")
    print("2. You must have proper permissions to purchase reserved instances")
    print("3. You have verified all purchase details above are correct")
    print()
    
    while True:
        confirmation = input("Do you want to execute ACTUAL Azure purchase API calls? (yes/no): ").strip().lower()
        if confirmation in ['yes', 'y']:
            return True
        elif confirmation in ['no', 'n']:
            return False
        else:
            print("Please enter 'yes' or 'no'")


def main():
    # Prompt user for input file name
    user_input = input(f"Enter input file name (default: {DEFAULT_INPUT_FILE}): ").strip()
    input_file = user_input if user_input else DEFAULT_INPUT_FILE
    
    file_path = os.path.join(INPUT_DIR, input_file)
    if not os.path.exists(file_path):
        print(f"Input file not found: {file_path}")
        return
    
    try:
        print("Step 1: Calculating reservation order details...")
        print("=" * 60)
        
        # Get Azure access token
        print("Getting Azure access token...")
        try:
            access_token = get_azure_access_token()
            print("✅ Successfully obtained Azure access token")
        except Exception as e:
            print(f"❌ Failed to get Azure access token: {e}")
            print("Please ensure you are authenticated with Azure:")
            print("1. Run: az login --use-device-code")
            print("2. Or ensure Azure SDK is properly configured")
            return
        
        # Step 1: Calculate reservation orders to get reservation order IDs
        calculation_results = calculate_reservation_order(file_path, access_token=access_token, save_to_csv=True)
        
        print(f"Successfully calculated {len(calculation_results)} reservation order(s).")
        print()
        
        # Debug: Print calculation responses for troubleshooting
        print("DEBUG: Calculation API Responses")
        print("-" * 40)
        for i, result in enumerate(calculation_results, 1):
            print(f"Response {i}:")
            print(f"Reservation Order ID: {result.get('reservation_order_id', 'N/A')}")
            print("Calculate Response:")
            print(json.dumps(result.get('calculate_response', {}), indent=2))
            print("-" * 40)
        print()
        
        # Step 2: Display purchase trigger summary and get user confirmation
        display_purchase_trigger_summary(calculation_results)
        
        if not get_user_confirmation():
            print("Operation cancelled by user. Please update your purchase trigger fields and try again.")
            return
        
        print()
        print("Step 3: Generating purchase API payloads...")
        print("=" * 60)
        
        # Step 3: Generate purchase payloads using the calculated reservation order IDs
        purchase_payloads = generate_api_payloads_with_order_ids(calculation_results)
        
        for i, payload_info in enumerate(purchase_payloads, 1):
            reservation_order_id = payload_info['reservation_order_id']
            payload = payload_info['payload']
            
            print(f"Purchase Payload {i}:")
            print(f"PUT https://management.azure.com/providers/Microsoft.Capacity/reservationOrders/{reservation_order_id}?api-version={API_VERSION}")
            print(json.dumps(payload, indent=2))
            print()
        
        # Step 4: Optional Azure API execution
        if get_api_execution_confirmation():
            try:
                from azure_purchase_api import execute_purchase_api_calls
                print()
                print("Executing Azure Purchase API calls...")
                print("=" * 60)
                
                results = execute_purchase_api_calls(purchase_payloads, API_VERSION, access_token=access_token)
                
                # Save results to file
                results_file = os.path.join(INPUT_DIR, f"purchase_results_{input_file.replace('.csv', '')}.json")
                with open(results_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"\nPurchase results saved to: {results_file}")
                
            except ImportError as e:
                print(f"Error importing Azure SDK: {e}")
                print("Please ensure Azure SDK packages are installed:")
                print("pip install azure-identity azure-core")
            except Exception as e:
                print(f"Error executing Azure API calls: {e}")
        else:
            print("\nAzure API execution skipped. Payloads are ready for manual execution.")
            
    except Exception as e:
        print(f"Error processing file: {e}")
        print("Please check that the file format and column names match the expected structure.")

if __name__ == "__main__":
    main()
