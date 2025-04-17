import smartsheet
from loguru import logger


def add_row_obj(cell_value, name, row, tracker):
    row.cells.append({
        'column_id':tracker._column_map[name],
        'value' : cell_value,
        'strict' : False})
    return row

def new_cell(column_name, cell_value, row, sheet, controller, tracker):
    cell = smartsheet.models.Cell()
    cell.column_id = tracker._column_map[column_name]
    cell.value = cell_value

    new_row = smartsheet.models.Row()
    new_row.id = row.id
    new_row.cells.append(cell)

    controller.update_row(sheet, new_row)

def copy_from_report(controller, copy_columns, formula_columns, report, tracker, to_sheet_id, today):
    row_ids_copied =[]
    copy_rows = []

    month = today.strftime('%B').upper() + ' ' + today.strftime('%Y')

    logger.debug(f"getting row id for {month}")
    parent_cell_id = None
    for row in tracker.get_rows():
        if tracker.get_cell_by_column_name(row, 'INV Mth/Yr').value == month:
            parent_cell_id = row.id
    wm_nums = []
    logger.debug(f"Copying rows...")
    for row in report.get_rows():
        new_row = smartsheet.models.Row()
        new_row.to_bottom = True
        new_row.parent_id = parent_cell_id
        wm_num=None
        com_po = report.get_cell_by_column_name(row, 'COMCAST PO').value
        closeout = report.get_cell_by_column_name(row, 'Job Status').value
        bill = report.get_cell_by_column_name(row, 'Billable').value
        if com_po and com_po != 'NO PO' and closeout == "CLOSEOUT" and bill == "YES":
            #change closeout to closed here
            for name in copy_columns:
                if name == 'Primary':
                    cell = report.get_cell_by_column_name(row, 'SITE ID')
                    new_row = add_row_obj(cell.value, 'SITE ID', new_row, tracker)
                elif name == 'Secured Date':
                    cell = report.get_cell_by_column_name(row, name)
                    new_row = add_row_obj(cell.value, 'Secured Date (from tracker)', new_row, tracker)
                else:
                    cell = report.get_cell_by_column_name(row, name)
                    if name == 'WORK MARKET #':
                        wm_num = int(report.get_cell_by_column_name(row, name).value)
                    new_row = add_row_obj(cell.value, name, new_row, tracker)
            for col in tracker.get_columns():
                if col.title in formula_columns:
                    new_row.cells.append({
                        'column_id':tracker._column_map[col.title],
                        'formula' : col.description,
                        'strict' : False})
            wm_exists = False
            for row in tracker.get_rows():
                tracker_wm_num = tracker.get_cell_by_column_name(row, 'WORK MARKET #').value
                com_po_exists = False
                if tracker_wm_num:
                    if (wm_num == int(tracker_wm_num)) or (wm_num in wm_nums):
                        wm_exists=True
                        for trow in tracker.get_rows():
                            tracker_com_po = tracker.get_cell_by_column_name(trow, 'COMCAST PO').value
                            print(tracker_com_po)
                            print(com_po)
                            if tracker_com_po and com_po == tracker_com_po:                            
                                com_po_exists=True
            if not wm_exists and not com_po_exists:
                wm_nums.append(wm_num)
                copy_rows.append(new_row)
    logger.debug(f"Pasting rows...")
    response = controller.add_rows(to_sheet_id, copy_rows)
    for row in response.result:
        row_ids_copied.append(row.id)

    return row_ids_copied

def add_billable_hours(controller, row_ids, tracker_id):
    tracker_upd = controller.get_sheet(tracker_id)
    logger.debug(f"Comparing WM hours to tracked hours...")
    for row_id in row_ids:
        row = controller.get_row_by_id(tracker_id, row_id)
        raw_hours_var = tracker_upd.get_cell_by_column_name(row, 'Total Hours Onsite from Main Tracker').value
        if raw_hours_var and "INVALID" not in str(raw_hours_var):
            raw_hours = float(raw_hours_var)
        else:
            raw_hours=0.0
        hours_rounded = round(raw_hours*4)/4
        if hours_rounded < 2 and hours_rounded != 0.0:
            hours_rounded = 2
        raw_WM_hours = tracker_upd.get_cell_by_column_name(row, 'WM Hours').value
        if raw_WM_hours and raw_WM_hours != '#NO MATCH':
            WM_hours_rounded = round(raw_WM_hours*4)/4
            if WM_hours_rounded < 2:
                WM_hours_rounded =2 
            if abs(hours_rounded - WM_hours_rounded) > 1:
                logger.debug("Major difference, rasing concern")
                comment = "There is a discrepency greater than 1 hour between WM hours and tracked hours"
                controller.create_discussion_on_row(row.sheet_id, row.id, comment)
            else:
                logger.debug("Difference negligible, taking tracker hours")
                new_cell('OA Billable Hours', hours_rounded, row, tracker_upd, controller, tracker_upd)
        else:
            logger.debug("No WM hours found, taking tracker hours")
            new_cell('OA Billable Hours', hours_rounded, row, tracker_upd, controller, tracker_upd)