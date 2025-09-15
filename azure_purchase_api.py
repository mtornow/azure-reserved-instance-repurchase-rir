"""
Module for executing Azure Reserved Instance purchase API calls using Azure Python SDK.
This module takes the generated payloads and makes actual REST API calls to Azure.
"""

import json
import time
from typing import List, Dict, Any
from azure.identity import DefaultAzureCredential
from azure.core.rest import HttpRequest
from azure.core.pipeline.transport import RequestsTransport
from azure.core.pipeline import Pipeline
from azure.core.pipeline.policies import (
    BearerTokenCredentialPolicy,
    RetryPolicy,
    HeadersPolicy
)


class AzurePurchaseAPI:
    """Class to handle Azure Reserved Instance purchase API calls"""
    
    def __init__(self, access_token=None):
        """
        Initialize the Azure client with access token or default credentials
        
        Args:
            access_token: Optional access token string. If provided, uses token-based auth.
                         If None, falls back to DefaultAzureCredential.
        """
        self.scope = "https://management.azure.com/.default"
        
        if access_token:
            # Use provided access token
            self.access_token = access_token
            self.use_token_auth = True
            
            # Create pipeline with manual token header
            policies = [
                HeadersPolicy({
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}"
                }),
                RetryPolicy(retry_total=3, retry_backoff_factor=1.0)
            ]
        else:
            # Use DefaultAzureCredential
            self.credential = DefaultAzureCredential()
            self.use_token_auth = False
            
            # Create pipeline with credential policy
            policies = [
                HeadersPolicy({"Content-Type": "application/json"}),
                BearerTokenCredentialPolicy(self.credential, self.scope),
                RetryPolicy(retry_total=3, retry_backoff_factor=1.0)
            ]
        
        self.pipeline = Pipeline(
            transport=RequestsTransport(),
            policies=policies
        )
    
    def execute_purchase_request(self, reservation_order_id: str, payload: Dict[str, Any], api_version: str = "2022-11-01") -> Dict[str, Any]:
        """
        Execute a single purchase API request
        
        Args:
            reservation_order_id: The reservation order ID for the purchase
            payload: The JSON payload for the purchase request
            api_version: The API version to use
            
        Returns:
            Dictionary containing the response details
        """
        url = f"https://management.azure.com/providers/Microsoft.Capacity/reservationOrders/{reservation_order_id}?api-version={api_version}"
        
        try:
            # Create the HTTP request
            request = HttpRequest(
                method="PUT",
                url=url,
                data=json.dumps(payload)
            )
            
            print(f"Executing purchase request for Reservation Order ID: {reservation_order_id}")
            print(f"URL: {url}")
            
            # Execute the request
            response = self.pipeline.run(request)
            
            # Parse response
            result = {
                "reservation_order_id": reservation_order_id,
                "status_code": response.http_response.status_code,
                "success": 200 <= response.http_response.status_code < 300,
                "url": url,
                "request_payload": payload
            }
            
            # Try to parse JSON response
            try:
                if response.http_response.content:
                    result["response_body"] = json.loads(response.http_response.content.decode('utf-8'))
                else:
                    result["response_body"] = {}
            except json.JSONDecodeError:
                result["response_body"] = {"raw_content": response.http_response.content.decode('utf-8', errors='ignore')}
            
            # Add response headers
            result["response_headers"] = dict(response.http_response.headers)
            
            return result
            
        except Exception as e:
            return {
                "reservation_order_id": reservation_order_id,
                "status_code": None,
                "success": False,
                "error": str(e),
                "url": url,
                "request_payload": payload,
                "response_body": {}
            }
    
    def execute_batch_purchases(self, purchase_payloads: List[Dict[str, Any]], api_version: str = "2022-11-01", delay_between_requests: float = 1.0) -> List[Dict[str, Any]]:
        """
        Execute multiple purchase API requests in sequence
        
        Args:
            purchase_payloads: List of payload dictionaries with 'reservation_order_id' and 'payload' keys
            api_version: The API version to use
            delay_between_requests: Delay in seconds between requests to avoid rate limiting
            
        Returns:
            List of response dictionaries
        """
        results = []
        
        print(f"Starting batch execution of {len(purchase_payloads)} purchase request(s)...")
        print("=" * 80)
        
        for i, payload_info in enumerate(purchase_payloads, 1):
            reservation_order_id = payload_info['reservation_order_id']
            payload = payload_info['payload']
            
            print(f"\n[{i}/{len(purchase_payloads)}] Processing reservation order: {reservation_order_id}")
            
            # Execute the request
            result = self.execute_purchase_request(reservation_order_id, payload, api_version)
            results.append(result)
            
            # Print result summary
            if result['success']:
                print(f"✅ SUCCESS - Status Code: {result['status_code']}")
            else:
                print(f"❌ FAILED - Status Code: {result.get('status_code', 'N/A')}")
                if 'error' in result:
                    print(f"Error: {result['error']}")
            
            # Add delay between requests (except for the last one)
            if i < len(purchase_payloads) and delay_between_requests > 0:
                print(f"Waiting {delay_between_requests} seconds before next request...")
                time.sleep(delay_between_requests)
        
        print("\n" + "=" * 80)
        print("Batch execution completed!")
        
        # Print summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        print(f"Summary: {successful} successful, {failed} failed out of {len(results)} total requests")
        
        return results
    
    def print_detailed_results(self, results: List[Dict[str, Any]]):
        """Print detailed results of the purchase operations"""
        print("\n" + "=" * 80)
        print("DETAILED RESULTS")
        print("=" * 80)
        
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Reservation Order ID: {result['reservation_order_id']}")
            print(f"Status: {'SUCCESS' if result['success'] else 'FAILED'}")
            print(f"Status Code: {result.get('status_code', 'N/A')}")
            print(f"URL: {result['url']}")
            
            if 'error' in result:
                print(f"Error: {result['error']}")
            
            if result.get('response_body'):
                print("Response Body:")
                print(json.dumps(result['response_body'], indent=2))
            
            print("-" * 60)


def execute_purchase_api_calls(purchase_payloads: List[Dict[str, Any]], api_version: str = "2022-11-01", access_token: str = None) -> List[Dict[str, Any]]:
    """
    Convenience function to execute purchase API calls
    
    Args:
        purchase_payloads: List of payload dictionaries from generate_api_payloads_with_order_ids
        api_version: Azure API version to use
        access_token: Optional access token for authentication
        
    Returns:
        List of response dictionaries
    """
    api_client = AzurePurchaseAPI(access_token=access_token)
    results = api_client.execute_batch_purchases(purchase_payloads, api_version)
    api_client.print_detailed_results(results)
    return results


if __name__ == "__main__":
    # Test the module with sample data
    print("Azure Purchase API module - Test mode")
    print("To use this module, import it in main.py or run main.py with actual data")
