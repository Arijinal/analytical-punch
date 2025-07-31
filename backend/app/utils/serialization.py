"""
Serialization utilities for converting numpy/pandas types to JSON-serializable formats
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Union
from datetime import datetime


def make_json_serializable(obj: Any) -> Any:
    """
    Convert numpy/pandas types to JSON-serializable Python types
    
    This ensures all data types are properly converted without shortcuts
    """
    # Handle numpy types
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        # Handle NaN and Infinity values
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return [make_json_serializable(item) for item in obj]
    
    # Handle pandas types
    elif isinstance(obj, pd.Timestamp):
        return int(obj.timestamp())
    elif isinstance(obj, pd.Series):
        return {
            str(k): make_json_serializable(v) 
            for k, v in obj.to_dict().items()
        }
    elif isinstance(obj, pd.DataFrame):
        return [
            {col: make_json_serializable(val) for col, val in row.items()}
            for _, row in obj.iterrows()
        ]
    
    # Handle datetime
    elif isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle dictionaries recursively
    elif isinstance(obj, dict):
        return {
            str(k): make_json_serializable(v) 
            for k, v in obj.items()
        }
    
    # Handle lists recursively
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    
    # Handle None and basic types
    elif obj is None or isinstance(obj, (str, int, bool)):
        return obj
    elif isinstance(obj, float):
        # Handle Python float NaN and Infinity
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    
    # For any other type, convert to string
    else:
        return str(obj)


def serialize_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Serialize a pandas DataFrame to a list of dictionaries
    with all values properly converted to JSON-serializable types
    """
    result = []
    
    for idx, row in df.iterrows():
        row_dict = {}
        
        # Handle index
        if isinstance(idx, pd.Timestamp):
            row_dict['timestamp'] = int(idx.timestamp())
        else:
            row_dict['index'] = make_json_serializable(idx)
        
        # Handle columns
        for col, val in row.items():
            row_dict[col] = make_json_serializable(val)
        
        result.append(row_dict)
    
    return result


def serialize_series(series: pd.Series) -> Dict[str, Any]:
    """
    Serialize a pandas Series to a dictionary
    with all values properly converted to JSON-serializable types
    """
    return {
        'name': series.name or 'series',
        'data': [
            {
                'index': make_json_serializable(idx),
                'value': make_json_serializable(val)
            }
            for idx, val in series.items()
        ]
    }