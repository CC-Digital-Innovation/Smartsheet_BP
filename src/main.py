import smartsheetcontrol
import smartsheetactions
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import openpyxl
import dotenv
import smtplib
from pathlib import PurePath
import os
from loguru import logger

dotenv.load_dotenv(PurePath(__file__).with_name('.env'))

smartsheet_controller = smartsheetcontrol.SmartsheetController(os.getenv('API_KEY'))


TODAY = datetime.now()


col_copy_list = ['Primary', 'WORK MARKET #', 'COMCAST PO', 'Job Status', 'Address', 'City', 'State', 'Zip Code', 'Secured Date']
formula_list = ['WM Status' , 'WM Date', 'Tech Name', 'Total Hours Onsite from Main Tracker', 'WM Hours', 'Billable (from Tracker)', 'Billable Expense Sell', "Hourly Sell"]
reports = os.getenv("REPORTS").split(',')
trackers = os.getenv("TRACKERS").split(',')
custnames = os.getenv("CUSTNAMES").split(',')


for submission in zip(custnames, reports, trackers):
    report = smartsheet_controller.get_report(submission[1])
    tracker = smartsheet_controller.get_sheet(submission[2])
    logger.debug(f"Copying closeout rows from {report.sheet.name} reort to {tracker.sheet.name}")
    rows_moved = smartsheetactions.copy_from_report(smartsheet_controller, col_copy_list, formula_list, report, tracker, submission[2], TODAY)
    if rows_moved:
        logger.debug(f"Filling in billable hours for {tracker.sheet.name}")
        smartsheetactions.add_billable_hours(smartsheet_controller, rows_moved['ids_copied'], submission[2])

        #Pull sheet one more time
        #sum hourly sell and billable exp sell collumns check for 0 values and flag
        #save notes data for excel template 
        logger.debug(f"Starting excel template")
        month = TODAY.strftime('%B') + ' ' + TODAY.strftime('%Y')
        excel_rows = []
                
        sell_sum = 0
        tracker_update = smartsheet_controller.get_sheet(submission[2])
        for row_id in rows_moved['ids_copied']:
            row = smartsheet_controller.get_row_by_id(submission[2], row_id)
            billable = tracker_update.get_cell_by_column_name(row, 'Billable Expense Sell').value
            hourly = tracker_update.get_cell_by_column_name(row, 'Hourly Sell').value
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
        logger.info(f"Weekly Total: {sell_sum}")

        #create excel template
        #column F is PO, M is month, P is Memo, S is amount, W is contract
        workbook = openpyxl.load_workbook(PurePath('src/template.xlsx'))
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

        date = TODAY.strftime("%m_%d_%Y")
        custname = submission[0]
        custname_file = custname.replace(' ', '_')
        xl_sheet_name = f'{custname_file}_{date}.xlsx'
        workbook.save(xl_sheet_name)

        logger.debug(f"Excel template finished")
        #email results
        sender = os.getenv('NOREPLYADDRESS')
        receiverlist = os.getenv('EMAILTO').split(',')
        subject = os.getenv('SUBJECT')
        message = MIMEMultipart("alternative")
        message["Subject"] = f"{subject} BILLING UPLOAD - {custname.upper()} - {sell_sum}"
        message["From"] = sender
        message["To"] = receiverlist[0]

        body = f"""
        Hello Team,
        
        The attached {custname} file has {len(excel_rows)} lines that total ${sell_sum}.
        
        Thank you,

        """

        message.attach(MIMEText(body))

        with open(xl_sheet_name, "rb") as raw:
            attachment = MIMEApplication(raw.read())	
        attachment.add_header('Content-Disposition', f"attachment; filename= {xl_sheet_name}") 
        message.attach(attachment)


        #Starts SMTP email server with TLS if enabled in config
        logger.debug("Starting SMTP server")
        serverName = os.getenv('MAILSERVER')
        Port = os.getenv('MAILPORT')
        server = smtplib.SMTP(serverName, Port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(os.getenv('SMTPUSERNAME'), os.getenv('SMTPPASSWORD'))



        # Sends email, and deletes temp files even if there was a problem sending the email
        logger.debug("Sending email")
        try:
            server.sendmail(sender, receiverlist, message.as_string())
        except Exception as e:
            logger.debug(e)
        finally:
            # Deletes temporary files
            logger.debug(f"Cleaning up")
            os.remove(xl_sheet_name)
        server.close()

        #close items in sheet
        #smartsheetactions.closeout(smartsheet_controller,  report, tracker, submission[2], rows_moved['rows_copied'], rows_moved['ids_copied'])
    else:
        logger.info(f"No items in closeout for {submission[0]}")
