import pandas as pd
import os

BASE_FILER_COLUMNS = {'Last Name', 'First Name'}

def find_column(df, keyword):
    kw = keyword.lower()
    for col in df.columns:
        if kw in str(col).lower():
            return col
    return None

def _get_or_create_filer(filers, row):
    last = row.get('Last Name')
    first = row.get('First Name')
    if pd.isna(last) or pd.isna(first):
        return None
    key = (last, first, row.get('Agency'))
    if key not in filers:
        filers[key] = {
            'last_name': last,
            'first_name': first,
            'agency': row.get('Agency'),
            'position': row.get('Position'),
            'filing_year': row.get('Filing Year'),
            'schedules': {
                'A-1': [],
                'A-2': [],
                'B': [],
                'C': [],
                'D': [],
                'E': [],
            }
        }
    return filers[key]

def _clean_columns(columns):
    return ["" if pd.isna(col) else str(col).strip() for col in columns]

def _row_has_filer_identity(row):
    return not pd.isna(row.get('Last Name')) and not pd.isna(row.get('First Name'))

def _fix_header(df):
    df.columns = _clean_columns(df.columns)
    columns = set(df.columns)
    if not BASE_FILER_COLUMNS.issubset(columns):
        df.columns = _clean_columns(df.iloc[0])
        df = df.drop(index=0).reset_index(drop=True)
        if not df.empty and not _row_has_filer_identity(df.iloc[0]):
            df = df.drop(index=0).reset_index(drop=True)
    return df

def normalize_shf(file, verbose: bool = False):
    _, file_extension = os.path.splitext(file)
    if file_extension != '.xlsx':
        if verbose:
            print("not a 700 form..")
        return []

    filers = {}
    seven_form = pd.read_excel(file, sheet_name=None)

    for sheet_name, df in seven_form.items():
        if verbose:
            print(f"Processing: {sheet_name}")
        df = _fix_header(df)
        sheet_lower = sheet_name.lower()

        if 'cover' in sheet_lower:
            pass

        elif 'schedule a-1' in sheet_lower or 'schedule a1' in sheet_lower:
            for _, row in df.iterrows():
                filer = _get_or_create_filer(filers, row)
                if filer is None:
                    continue
                filer['schedules']['A-1'].append({
                    'schedule': 'A-1',
                    'business_entity': row.get('NAME OF BUSINESS ENTITY'),
                })

        elif 'schedule a-2' in sheet_lower:
            for _, row in df.iterrows():
                filer = _get_or_create_filer(filers, row)
                if filer is None:
                    continue
                filer['schedules']['A-2'].append({
                    'business_entity': row.get('NAME OF BUSINESS ENTITY OR TRUST'),
                })

        elif 'schedule b' in sheet_lower:
            for _, row in df.iterrows():
                filer = _get_or_create_filer(filers, row)
                if filer is None:
                    continue
                filer['schedules']['B'].append({
                    'property_entity': row.get('STREET ADDRESS OR PRECISE LOCATION'),
                })

        elif 'schedule c - income section' in sheet_lower:
            for _, row in df.iterrows():
                filer = _get_or_create_filer(filers, row)
                if filer is None:
                    continue
                filer['schedules']['C'].append({
                    'name_of_source': row.get('NAME OF SOURCE'),
                    'business_activity': row.get('BUSINESS ACTIVITY, IF ANY'),
                })

        elif 'schedule d' in sheet_lower:
            for _, row in df.iterrows():
                filer = _get_or_create_filer(filers, row)
                if filer is None:
                    continue
                filer['schedules']['D'].append({
                    'name_of_source': row.get('NAME OF SOURCE'),
                    'gifts': row.get('DESCRIPTION OF GIFT(S)'),
                })

        elif 'schedule e' in sheet_lower:
            desc_col = find_column(df, "Description")
            for _, row in df.iterrows():
                filer = _get_or_create_filer(filers, row)
                if filer is None:
                    continue
                filer['schedules']['E'].append({
                    'name_of_source': row.get('NAME OF SOURCE'),
                    'description': row.get(desc_col) if desc_col else None,
                })

    return list(filers.values())

if __name__ == "__main__":
    file = "sac700.xlsx"
    print(normalize_shf(file))
