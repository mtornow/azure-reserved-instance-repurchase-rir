# Azure Reserved Instance Repurchase 

## ⚠️ DISCLAIMER

**This software is provided "as-is" to the best knowledge of the author(s). Use at your own risk.**

This tool interacts with Azure APIs and can result in real financial charges to your Azure subscription. The authors make no warranties, express or implied, regarding the accuracy, reliability, or suitability of this software for any particular purpose. Users are solely responsible for:

- Verifying all reservation parameters before execution
- Understanding Azure pricing and billing implications  
- Ensuring proper authentication and permissions
- Reviewing all API responses and charges

**By using this software, you acknowledge that you understand the risks and accept full responsibility for any charges, errors, or issues that may arise.**

---

This Python project reads a CSV file containing Azure Reserved Instance purchase parameters and generates Azure REST API PUT request payloads for each row.

## Features
- **Interactive file selection**: Prompts user for input file with default fallback
- Input: .csv file with columns matching the provided example
- Output: Formatted Azure REST API PUT request payloads
- **Four-step workflow**: Calculate API → Review & Confirm → Generate Payloads → Execute API Calls (optional)
- **Azure SDK Integration**: Automatic execution of purchase API calls using Azure Python SDK
- **Purchase trigger validation**: Interactive review of all purchase parameters before payload generation
- **Reservation Order ID generation**: Automatically generates and saves order IDs to CSV
- **Purchase confirmation gating**: Manual review and confirmation before purchase
- **Price calculation and display**: Shows calculated costs in simple format
- Handles both semicolon and comma-separated CSV files
- Robust file format detection and error handling

## Prerequisites

### Azure Authentication
Before running the script, you must authenticate with Azure:

```bash
az login --use-device-code
```

This will open a browser where you can authenticate with your Azure credentials. The script uses real Azure APIs and requires valid authentication to:
- Get accurate pricing information via the Calculate API
- Generate actual reservation order IDs
- Execute purchase API calls

**Note:** The script no longer uses mock responses. All calculations require real Azure API calls with valid authentication.

**Required Permissions:**
- Microsoft.Capacity/calculatePrice/action (for pricing calculations)
- Microsoft.Capacity/reservationOrders/write (for purchases)
- Access to the subscription(s) specified in your input file

## Usage
1. **Authenticate with Azure**: Run `az login --use-device-code` first
2. Place your input CSV file in the `input_file` directory.
3. Run: `python main.py`
4. When prompted, enter your file name or press Enter for the default example file
5. The script will:
   - **Step 1**: Calculate reservation order IDs using Azure Calculate API
   - **Step 2**: Display purchase trigger fields for user review and confirmation
   - **Step 3**: Generate purchase API payloads with the calculated order IDs (only if confirmed)
   - **Step 4**: Optionally execute actual Azure API calls to make purchases (⚠️ REAL CHARGES!)

## Complete Workflow

### Step 1: Run the Script
```bash
python main.py
```

### Interactive Process:
1. **File Selection**: Enter your input file name when prompted, or press Enter for default (`example_RI_purchase.csv`)
2. **Calculate Reservation Orders**: Script automatically calculates reservation order IDs and saves results
3. **Review Purchase Triggers**: Script displays all reservation details for your review:
   - Purchase Trigger status
   - SKU, Region, Quantity, Term, Billing Plan
   - Display Name and Reservation Order ID
   - Estimated Price
4. **Confirmation**: You must explicitly confirm (yes/no) to proceed with payload generation
5. **Generate Payloads**: If confirmed, script generates Azure REST API PUT request payloads
6. **Execute API Calls (Optional)**: Option to automatically execute the API calls using Azure SDK

#### ⚠️ Step 4: Execute Azure Purchase API Calls (OPTIONAL)
**WARNING: This step makes REAL Azure API calls that will result in ACTUAL charges!**

- The script will ask for confirmation before executing actual purchase API calls
- You must have authenticated with `az login --use-device-code` first
- You must have proper permissions to purchase reserved instances
- All API responses are saved to a JSON file for your records

Example confirmation prompt:
```
⚠️  WARNING: This will make ACTUAL Azure API calls to purchase reserved instances!
💰 This will result in REAL charges to your Azure subscription!

Do you want to execute ACTUAL Azure purchase API calls? (yes/no):
```

### Detailed Steps:

#### Step 1: Calculate Reservation Orders
- Read your input CSV file
- Call Azure Calculate API for each row
- Generate unique reservation order IDs
- Create a new CSV file: `{filename}_with_order_ids.csv`
- The new CSV includes:
  - All original columns
  - `ReservationOrderID` column with generated UUIDs
  - `Price` column with format "amount currency" (e.g., "46 USD")
  - `Purchased Confirmed` column (initially empty)

#### Step 2: Review Purchase Trigger Fields ⚠️ **NEW SAFETY STEP**
The script will display:
```
Reservation 1:
  - Purchase Trigger: 'Not Set'
  - SKU: standard_D1
  - Region: westus
  - Quantity: 1
  - Term: P1Y
  - Billing Plan: Monthly
  - Display Name: TestReservationOrder
  - Reservation Order ID: 00000000-0000-0000-0000-000000000000
  - Estimated Price: 46 USD
```

**IMPORTANT**: Review that:
1. Purchase Trigger fields are set correctly for automatic purchasing
2. All reservation details (SKU, region, quantity, etc.) are accurate  
3. You have reviewed the estimated prices

You must type **"yes"** to proceed or **"no"** to cancel and update your settings.

#### Step 3: Generate Purchase API Payloads
- Generate Azure REST API PUT request payloads only for confirmed reservations
- Output ready-to-use API requests with reservation order IDs

### Example Workflow
```
1. az login --use-device-code  # Authenticate with Azure first
2. python main.py
3. Enter file name: my_reservations.csv (or press Enter for default)
4. Review displayed purchase trigger fields and reservation details
5. Type "yes" to confirm and generate purchase API payloads
6. Type "yes" again to execute ACTUAL Azure API calls (optional)
   OR type "no" to skip API execution and use payloads manually
7. API results are saved to purchase_results_*.json file
```

## Requirements
- Python 3.8+
- Azure CLI (for authentication)
- pandas
- azure-identity
- azure-core

## Setup
```bash
pip install -r requirements.txt
```

## Expected Input Format
The input file should contain columns:
- Purchase Trigger
- SKU-name
- azure region  
- reservedResourceType
- subscription
- term
- billingPlan
- quantity
- displayName
- appliedScopes
- appliedScopeType
- InstanceFlexibility
- renew

### InstanceFlexibility Parameter Handling

The `InstanceFlexibility` parameter is handled conditionally based on the `reservedResourceType`:

#### VirtualMachines Resources
- **Required**: `InstanceFlexibility` column must be present and have a value
- **Values**: Typically `On` or `Off`
- **JSON Output**: Includes `reservedResourceProperties` with `instanceFlexibility` field

```csv
reservedResourceType,InstanceFlexibility
VirtualMachines,On
```

#### Non-VM Resources (PostgreSQL, CosmosDB, SQL Database, etc.)
- **Optional**: `InstanceFlexibility` column can be omitted or left empty
- **Behavior**: If provided, the value is ignored with a warning message
- **JSON Output**: `reservedResourceProperties` field is completely omitted

```csv
reservedResourceType,InstanceFlexibility
PostgreSql,
CosmosDb,
```

#### Warning Messages
When `InstanceFlexibility` values are provided for non-VM resources, you'll see:
```
⚠️  Warning: InstanceFlexibility value 'On' will be ignored for reservedResourceType 'PostgreSql' in row 1
```

#### Supported Resource Types
- **Requires InstanceFlexibility**: `VirtualMachines`
- **Ignores InstanceFlexibility**: `PostgreSql`, `CosmosDb`, `SqlDatabase`, `RedisCache`, and other non-VM services

### Applied Scopes Configuration

Reserved Instances can be scoped in different ways using the `appliedScopeType` and `appliedScopes` columns:

#### 1. Shared Scope (Subscription-wide)
- **appliedScopeType**: `Shared`
- **appliedScopes**: Leave empty or use empty string
- **Description**: Reservation applies to all matching resources in the subscription

```csv
appliedScopeType,appliedScopes
Shared,
```

#### 2. Single Scope (Resource Group-specific)
- **appliedScopeType**: `Single`
- **appliedScopes**: Full resource group path
- **Description**: Reservation applies only to matching resources in the specified resource group

```csv
appliedScopeType,appliedScopes
Single,/subscriptions/YOUR-SUBSCRIPTION-ID/resourceGroups/YOUR-RESOURCE-GROUP-NAME
```

#### Example Resource Group Scoping
For a reservation scoped to a specific resource group:

```csv
Purchase Trigger;SKU-name;azure region;reservedResourceType;subscription;term;billingPlan;quantity;displayName;appliedScopes;appliedScopeType;InstanceFlexibility;renew
;Standard_D2s_v3;eastus;VirtualMachines;YOUR-SUBSCRIPTION-ID;P1Y;Monthly;2;MyVMReservation;/subscriptions/YOUR-SUBSCRIPTION-ID/resourceGroups/YOUR-RESOURCE-GROUP-NAME;Single;On;No
```

**Important Notes:**
- Replace `YOUR-SUBSCRIPTION-ID` with your actual Azure subscription ID
- Replace `YOUR-RESOURCE-GROUP-NAME` with your actual resource group name
- The resource group must exist in the specified subscription
- Single scope provides more granular cost allocation and resource targeting

## Generated CSV Output
The script generates a CSV file with additional columns:
- **ReservationOrderID**: Generated UUID for each reservation
- **Price**: Calculated cost in format "amount currency" (e.g., "46 USD")  
- **Purchased Confirmed**: Empty column for manual confirmation (set to 1, Y, yes, or Yes to confirm purchase)

## Output
Generates Azure REST API PUT requests in the format:
```
PUT https://management.azure.com/providers/Microsoft.Capacity/reservationOrders/{orderId}?api-version=2022-11-01
{JSON payload}
```
