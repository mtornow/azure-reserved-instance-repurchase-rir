"""
Module for generating JSON payloads from input files for Azure Reserved Instance API calls.
"""

import pandas as pd
import os


def read_input_file(file_path):
    """Read input file (CSV only) and return DataFrame"""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.csv':
        # Try different separators
        try:
            df = pd.read_csv(file_path, sep=';')
        except:
            try:
                df = pd.read_csv(file_path, sep=',')
            except:
                df = pd.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_ext}. Only CSV files are supported.")
    
    return df


def generate_api_payloads(file_path, reservation_order_id=None):
    """Generate API payloads from input file with optional reservation order ID"""
    df = read_input_file(file_path)
    payloads = []
    for index, row in df.iterrows():
        # Validate required columns exist
        required_columns = ["appliedScopes", "appliedScopeType"]
        for col in required_columns:
            if col not in row:
                raise ValueError(f"Missing required column: {col} in row {index + 1}")
        
        # Get the scope type and validate it
        if pd.isna(row["appliedScopeType"]):
            raise ValueError(f"Missing or empty appliedScopeType in row {index + 1}")
            
        scope_type = str(row["appliedScopeType"]).strip().lower()
        if scope_type not in ["single", "shared", "managementgroup"]:
            raise ValueError(f"Invalid appliedScopeType: '{row['appliedScopeType']}' in row {index + 1}. Must be 'Single', 'Shared', or 'ManagementGroup'")
        
        # Handle appliedScopes based on appliedScopeType
        applied_scopes_value = row.get("appliedScopes", "")
        
        # Convert NaN to empty string for processing
        if pd.isna(applied_scopes_value):
            applied_scopes_value = ""
        else:
            applied_scopes_value = str(applied_scopes_value).strip()
        
        applied_scopes = None
        if scope_type == "single":
            # For Single scope type, appliedScopes must be provided and should be an array with one element
            if not applied_scopes_value:
                raise ValueError(f"appliedScopes is required when appliedScopeType is 'Single' in row {index + 1}. Please provide a subscription or resource group scope.")
            applied_scopes = [applied_scopes_value]
        elif scope_type in ["shared", "managementgroup"]:
            # For Shared or ManagementGroup scope types, appliedScopes should be null/None
            # But if provided, we'll ignore it with a warning
            if applied_scopes_value:
                print(f"Warning: appliedScopes value '{applied_scopes_value}' will be ignored for appliedScopeType '{row['appliedScopeType']}' in row {index + 1}")
            applied_scopes = None

        # Build reservedResourceProperties based on resource type
        reserved_resource_properties = {}
        resource_type = str(row["reservedResourceType"]).strip()
        
        # instanceFlexibility is only applicable for VirtualMachines
        if resource_type.lower() == "virtualmachines":
            if "InstanceFlexibility" not in row or pd.isna(row["InstanceFlexibility"]):
                raise ValueError(f"InstanceFlexibility is required when reservedResourceType is 'VirtualMachines' in row {index + 1}")
            reserved_resource_properties["instanceFlexibility"] = row["InstanceFlexibility"]
        else:
            # For non-VM resources, instanceFlexibility parameter is skipped entirely
            # But if it's provided, we'll show a warning
            if "InstanceFlexibility" in row and not pd.isna(row["InstanceFlexibility"]) and str(row["InstanceFlexibility"]).strip():
                print(f"⚠️  Warning: InstanceFlexibility value '{row['InstanceFlexibility']}' will be ignored for reservedResourceType '{resource_type}' in row {index + 1}")

        # Build the properties object
        properties = {
            "reservedResourceType": row["reservedResourceType"],
            "billingScopeId": f"/subscriptions/{row['subscription']}",
            "term": row["term"],
            "billingPlan": row["billingPlan"],
            "quantity": int(row["quantity"]),
            "displayName": row["displayName"],
            "appliedScopes": applied_scopes,
            "appliedScopeType": row["appliedScopeType"],
            "renew": str(row["renew"]).strip().lower() == "yes"
        }
        
        # Only include reservedResourceProperties if it has content
        if reserved_resource_properties:
            properties["reservedResourceProperties"] = reserved_resource_properties
        
        payload = {
            "sku": {"name": row["SKU-name"]},
            "location": row["azure region"],
            "properties": properties
        }
        payloads.append({
            'payload': payload,
            'reservation_order_id': reservation_order_id
        })
    return payloads


def is_purchase_confirmed(value):
    """Check if the purchase confirmation value indicates confirmed purchase"""
    if pd.isna(value):
        return False
    value_str = str(value).strip().lower()
    return value_str in ['1', 'y', 'yes']


def is_purchase_trigger_set(value):
    """Check if the purchase trigger value indicates purchase should proceed"""
    if pd.isna(value):
        return False
    value_str = str(value).strip().lower()
    return value_str in ['1', 'y', 'yes']


def generate_api_payloads_with_order_ids(calculation_results):
    """Generate API payloads using reservation order IDs from calculate results, filtered by purchase trigger and confirmation"""
    payloads = []
    skipped_no_trigger = 0
    skipped_no_confirmation = 0
    
    for result in calculation_results:
        row = result['input_row']
        reservation_order_id = result['reservation_order_id']
        
        # Check if purchase trigger is set (primary safety check)
        if 'Purchase Trigger' in row and not is_purchase_trigger_set(row['Purchase Trigger']):
            skipped_no_trigger += 1
            continue
        
        # Check if purchase is confirmed (secondary safety check - only if the column exists)
        if 'Purchased Confirmed' in row and not is_purchase_confirmed(row['Purchased Confirmed']):
            skipped_no_confirmation += 1
            continue
        
        # Handle appliedScopes based on appliedScopeType
        applied_scopes = None
        if not pd.isna(row["appliedScopes"]) and row["appliedScopes"] != '':
            if row["appliedScopeType"].lower() == "single":
                # For Single scope type, appliedScopes should be an array with one element
                applied_scopes = [row["appliedScopes"]]
            else:
                # For other scope types (like Shared), appliedScopes should be null/None
                applied_scopes = None

        # Build reservedResourceProperties based on resource type
        reserved_resource_properties = {}
        resource_type = str(row["reservedResourceType"]).strip()
        
        # instanceFlexibility is only applicable for VirtualMachines
        if resource_type.lower() == "virtualmachines":
            if "InstanceFlexibility" not in row or pd.isna(row["InstanceFlexibility"]):
                raise ValueError(f"InstanceFlexibility is required when reservedResourceType is 'VirtualMachines'")
            reserved_resource_properties["instanceFlexibility"] = row["InstanceFlexibility"]
        else:
            # For non-VM resources, instanceFlexibility parameter is skipped entirely
            # But if it's provided, we'll show a warning
            if "InstanceFlexibility" in row and not pd.isna(row["InstanceFlexibility"]) and str(row["InstanceFlexibility"]).strip():
                print(f"⚠️  Warning: InstanceFlexibility value '{row['InstanceFlexibility']}' will be ignored for reservedResourceType '{resource_type}'")

        # Build the properties object
        properties = {
            "reservedResourceType": row["reservedResourceType"],
            "billingScopeId": f"/subscriptions/{row['subscription']}",
            "term": row["term"],
            "billingPlan": row["billingPlan"],
            "quantity": int(row["quantity"]),
            "displayName": row["displayName"],
            "appliedScopes": applied_scopes,
            "appliedScopeType": row["appliedScopeType"],
            "renew": str(row["renew"]).strip().lower() == "yes"
        }
        
        # Only include reservedResourceProperties if it has content
        if reserved_resource_properties:
            properties["reservedResourceProperties"] = reserved_resource_properties
        
        payload = {
            "sku": {"name": row["SKU-name"]},
            "location": row["azure region"],
            "properties": properties
        }
        payloads.append({
            'payload': payload,
            'reservation_order_id': reservation_order_id
        })
    
    # Print summary of skipped rows
    total_skipped = skipped_no_trigger + skipped_no_confirmation
    if total_skipped > 0:
        print(f"Skipped {total_skipped} row(s):")
        if skipped_no_trigger > 0:
            print(f"  - {skipped_no_trigger} row(s) where 'Purchase Trigger' was not set to 1, Y, yes, or Yes")
        if skipped_no_confirmation > 0:
            print(f"  - {skipped_no_confirmation} row(s) where 'Purchased Confirmed' was not set to 1, Y, yes, or Yes")
    
    return payloads
