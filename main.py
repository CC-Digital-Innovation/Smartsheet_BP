import smartsheetcontrol
import smartsheetactions
from datetime import datetime
import openpyxl
import dotenv
from pathlib import PurePath
import os
from loguru import logger

dotenv.load_dotenv(PurePath(__file__).with_name('.env'))

smartsheet_controller = smartsheetcontrol.SmartsheetController(os.getenv('api_key'))


TODAY = datetime.now()


col_copy_list = ['Primary', 'WORK MARKET #', 'COMCAST PO', 'Job Status', 'Address', 'City', 'State', 'Zip Code', 'Secured Date']
formula_list = ['WM Status' , 'WM Date', 'Tech Name', 'Total Hours Onsite from Main Tracker', 'WM Hours', 'Billable (from Tracker)', 'Billable Expense Sell', "Hourly Sell"]
report = smartsheet_controller.get_report(os.getenv("reports"))
tracker = smartsheet_controller.get_sheet(os.getenv("trackers"))
logger.debug(f"Copying closeout rows from {report.sheet.name} reort to {tracker.sheet.name}")
rows_moved = smartsheetactions.copy_from_report(smartsheet_controller, col_copy_list, formula_list, report, tracker, os.getenv("trackers"), TODAY)
logger.debug(f"Filling in billable hours for {tracker.sheet.name}")
smartsheetactions.add_billable_hours(smartsheet_controller, rows_moved, os.getenv("trackers"))

#Pull sheet one more time
#sum hourly sell and billable exp sell collumns check for 0 values and flag
#save notes data for excel template 
logger.debug(f"Starting excel template")
month = TODAY.strftime('%B') + ' ' + TODAY.strftime('%Y')
excel_rows = []
        
sell_sum = 0
tracker_update = smartsheet_controller.get_sheet(os.getenv("trackers"))
for row_id in rows_moved:
    row = smartsheet_controller.get_row_by_id(os.getenv("trackers"), row_id)
    billable = tracker_update.get_cell_by_column_name(row, 'Billable Expense Sell').value
    hourly = tracker_update.get_cell_by_column_name(row, 'Hrly Sell').value
    excel_time_row = {}
    excel_travel_row = {}
    if (billable and hourly) and (billable > 0):
        sell_sum =sell_sum + billable + hourly
        excel_time_row['site id'] = tracker_update.get_cell_by_column_name(row, 'COMCAST PO').value
        excel_time_row['memo'] = tracker_update.get_cell_by_column_name(row, 'OA Timesheet Note').value
        excel_time_row['contract'] = tracker_update.get_cell_by_column_name(row, 'OA Task Name').value
        excel_time_row['amount'] = tracker_update.get_cell_by_column_name(row, 'Hourly Sell').value
        excel_travel_row['site id'] = tracker_update.get_cell_by_column_name(row, 'COMCAST PO').value
        excel_travel_row['memo'] = tracker_update.get_cell_by_column_name(row, 'Expense Notes').value
        excel_travel_row['contract'] = tracker_update.get_cell_by_column_name(row, 'OA Task Name').value
        excel_travel_row['amount'] = tracker_update.get_cell_by_column_name(row, 'Billable Expense Sell').value
        excel_rows.append(excel_time_row)
        excel_rows.append(excel_travel_row)
print(sell_sum)

#create excel template
#column F is PO, M is month, P is Memo, S is amount, W is contract
workbook = openpyxl.load_workbook('template.xlsx')
excel_sheet = workbook.active
row_start=8
for row in excel_rows:
    po_cell = excel_sheet['F' + str(row_start)]
    po_cell.value = row['site id']
    month_cell = excel_sheet['M' + str(row_start)]
    month_cell.value = month
    memo_cell = excel_sheet['P' + str(row_start)]
    memo_cell.value = row['memo']
    amount_cell = excel_sheet['S' + str(row_start)]
    amount_cell.value = row['amount']
    contract_cell = excel_sheet['W' + str(row_start)]
    contract_cell.value = row['contract']
    row_start = row_start + 1


workbook.save('template_filled.xlsx')

logger.debug(f"Excel template finished")
#email results
