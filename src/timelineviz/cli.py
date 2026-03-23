"""
Command-line interface for the timeline visualization library.

This module provides a command-line tool for generating timeline visualizations
from CSV files without writing Python code.
"""

import argparse
import os
import sys
import json
import pandas as pd
from timelineviz.timeline import (
    plot_multiple_timelines,
    plot_event_log_timeline,
    DEFAULT_COLOR_SCHEME,
)
from timelineviz.utils import create_color_scheme
from timelineviz.promtest import parse_promtest_file, plot_promtest

def parse_args(args=None):
    """Parse command line arguments.
    
    Parameters:
    -----------
    args : list, optional
        Command line arguments. If None, uses sys.argv[1:]
    """
    parser = argparse.ArgumentParser(
        description='Generate timeline visualizations from CSV data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Generate timelines using auto-detected timestamp columns:
  timelineviz data.csv --output-dir timelines --detect-timestamps
  
  # Specify timestamp columns:
  timelineviz data.csv --timestamp-columns created_at updated_at completed_at
  
  # Set entity identifier column and name:
  timelineviz patients.csv --id-column patient_id --entity-name Patient
  
  # Use custom color scheme:
  timelineviz orders.csv --colors '{"line":"#336699","point_face":"#FFCC00"}'
  
  # Set custom label mappings:
  timelineviz events.csv --label-mappings '{"created_at":"Creation Date","completed_at":"Completion"}'
  
  # Process a specific number of entities:
  timelineviz large_data.csv --max-entities 5

  # Long-format log: one timestamp column, many rows (filter by level/type):
  timelineviz incident.csv --event-log --log-time-column ts \\
    --log-label-column message --log-filter-column level \\
    --log-include ERROR WARN --output-dir out
"""
    )
    
    parser.add_argument('csv_file', help='CSV file containing timestamp data')
    
    parser.add_argument(
        '--timestamp-columns', '-t', 
        nargs='+', 
        help='Column names containing timestamps'
    )
    
    parser.add_argument(
        '--detect-timestamps', '-d',
        action='store_true',
        help='Automatically detect timestamp columns'
    )
    
    parser.add_argument(
        '--id-column', '-i',
        help='Column name for entity identifier'
    )
    
    parser.add_argument(
        '--entity-name', '-e',
        default='Entity',
        help='Name to use for entities in titles (e.g., Patient, Order, User)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        help='Directory to save timeline images'
    )
    
    parser.add_argument(
        '--max-entities', '-m',
        type=int,
        help='Maximum number of entities to process'
    )
    
    parser.add_argument(
        '--threshold-days', '-T',
        type=float,
        default=1.0,
        help='Number of days gap to consider as a break in timeline'
    )
    
    parser.add_argument(
        '--figsize', 
        default='15,5',
        help='Figure size in inches (width,height)'
    )
    
    parser.add_argument(
        '--point-size',
        type=int,
        default=10,
        help='Size of the event points'
    )
    
    parser.add_argument(
        '--colors', '-c',
        help='JSON string with custom color scheme'
    )
    
    parser.add_argument(
        '--label-mappings', '-l',
        help='JSON string with custom label mappings'
    )
    
    parser.add_argument(
        '--remove-suffixes', '-r',
        nargs='+',
        help='Suffixes to remove when creating labels'
    )
    
    parser.add_argument(
        '--no-show',
        action='store_true',
        help="Don't display plots (only save to files)"
    )
    
    parser.add_argument(
        '--dpi',
        type=int,
        default=150,
        help='Resolution for saved images'
    )

    parser.add_argument(
        '--promtest',
        action='store_true',
        help='Treat input as a promtool unit-test YAML file and visualise series/alerts'
    )

    parser.add_argument(
        '--event-log',
        action='store_true',
        help='Long-format mode: one timestamp column across many rows (see --log-*)'
    )
    parser.add_argument(
        '--log-time-column',
        metavar='COL',
        help='Timestamp column (required with --event-log)'
    )
    parser.add_argument(
        '--log-label-column',
        metavar='COL',
        help='Column to use as the text label for each event'
    )
    parser.add_argument(
        '--log-filter-column',
        metavar='COL',
        help='Column for --log-include / --log-exclude (e.g. level, event_type)'
    )
    parser.add_argument(
        '--log-include',
        nargs='+',
        metavar='VALUE',
        help='Keep only rows where the filter column equals one of these values'
    )
    parser.add_argument(
        '--log-exclude',
        nargs='+',
        metavar='VALUE',
        help='Drop rows where the filter column equals one of these values'
    )
    
    # Parse the arguments
    args = parser.parse_args(args)
    
    # Validate figure size format
    try:
        width, height = map(float, args.figsize.split(','))
    except ValueError:
        parser.error("Figure size must be in format 'width,height'")
    
    # Convert JSON strings to dicts
    if args.colors:
        try:
            args.colors = json.loads(args.colors)
        except json.JSONDecodeError:
            parser.error("Invalid JSON format for --colors")
            
    if args.label_mappings:
        try:
            args.label_mappings = json.loads(args.label_mappings)
        except json.JSONDecodeError:
            parser.error("Invalid JSON format for --label-mappings")

    if args.event_log and args.promtest:
        parser.error("--event-log cannot be combined with --promtest")
    if args.event_log and not args.log_time_column:
        parser.error("--event-log requires --log-time-column")
            
    return args

def main(args=None):
    """Main entry point for the CLI tool.
    
    Parameters:
    -----------
    args : list, optional
        Command line arguments. If None, uses sys.argv[1:]
    """
    if args is None:
        args = sys.argv[1:]
    
    args = parse_args(args)
    
    # Validate input file exists
    if not os.path.isfile(args.csv_file):
        print(f"Error: File '{args.csv_file}' not found", file=sys.stderr)
        return 1

    # --- Event log (long-format) mode ---
    if args.event_log:
        return _run_event_log(args)

    # --- Promtest mode ---
    if args.promtest:
        return _run_promtest(args)
    
    # Parse figure size
    try:
        figsize = tuple(map(float, args.figsize.split(',')))
        if len(figsize) != 2:
            raise ValueError("Figure size must be width,height")
    except ValueError as e:
        print(f"Error parsing figure size: {e}", file=sys.stderr)
        return 1
    
    # Initialize color_scheme
    color_scheme = None
    
    # Validate color scheme if provided
    if args.colors:
        required_keys = [
            'line', 'point_edge', 'point_face', 'connector',
            'label_bg', 'label_edge', 'slashes', 'title'
        ]
        missing_keys = [key for key in required_keys if key not in args.colors]
        if missing_keys:
            print(f"Error: Missing required color keys: {missing_keys}")
            return 1
        
        # Validate each color value
        try:
            color_scheme = create_color_scheme(
                base_color=args.colors.get('line'),
                accent_color=args.colors.get('point_face')
            )
        except ValueError as e:
            print(f"Error: Invalid color scheme: {e}")
            return 1
    
    # Validate label mappings if provided (wide CSV mode only)
    if args.label_mappings and not args.event_log:
        # Read CSV to get column names
        df = pd.read_csv(args.csv_file)
        invalid_columns = [col for col in args.label_mappings if col not in df.columns]
        if invalid_columns:
            print(f"Error: Label mappings reference non-existent columns: {invalid_columns}")
            return 1
    
    # Check if either timestamp columns or detection are specified
    if not args.timestamp_columns and not args.detect_timestamps and not args.event_log:
        print("Warning: No timestamp columns specified and auto-detection disabled.", 
              "Will attempt to detect common timestamp column patterns anyway.",
              file=sys.stderr)
        args.detect_timestamps = True
    
    # Generate the timelines
    try:
        processed = plot_multiple_timelines(
            data=args.csv_file,
            timestamp_columns=args.timestamp_columns,
            id_column=args.id_column,
            detect_timestamps=args.detect_timestamps,
            output_dir=args.output_dir,
            max_entities=args.max_entities,
            threshold_days=args.threshold_days,
            figsize=figsize,
            point_size=args.point_size,
            color_scheme=color_scheme,
            show_plots=not args.no_show,
            dpi=args.dpi,
            label_mappings=args.label_mappings,
            remove_suffixes=args.remove_suffixes,
            entity_name=args.entity_name
        )
        
        if not processed:
            print("No timelines were generated. Check your input data and parameters.", 
                  file=sys.stderr)
            return 1
        
        print(f"Successfully processed {len(processed)} timelines.")
        return 0
        
    except Exception as e:
        print(f"Error generating timelines: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

def _run_event_log(args):
    """Handle --event-log mode."""
    try:
        figsize = tuple(map(float, args.figsize.split(',')))
        if len(figsize) != 2:
            raise ValueError("Figure size must be width,height")
    except ValueError as e:
        print(f"Error parsing figure size: {e}", file=sys.stderr)
        return 1

    color_scheme = None
    if args.colors:
        required_keys = [
            'line', 'point_edge', 'point_face', 'connector',
            'label_bg', 'label_edge', 'slashes', 'title'
        ]
        missing_keys = [key for key in required_keys if key not in args.colors]
        if missing_keys:
            print(f"Error: Missing required color keys: {missing_keys}", file=sys.stderr)
            return 1
        try:
            color_scheme = create_color_scheme(
                base_color=args.colors.get('line'),
                accent_color=args.colors.get('point_face')
            )
        except ValueError as e:
            print(f"Error: Invalid color scheme: {e}", file=sys.stderr)
            return 1

    output_file = None
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        output_file = os.path.join(args.output_dir, 'event_log_timeline.png')

    try:
        fig, _axs = plot_event_log_timeline(
            data=args.csv_file,
            timestamp_column=args.log_time_column,
            label_column=args.log_label_column,
            filter_column=args.log_filter_column,
            include_values=args.log_include,
            exclude_values=args.log_exclude,
            threshold_days=args.threshold_days,
            figsize=figsize,
            point_size=args.point_size,
            color_scheme=color_scheme,
            show_plot=not args.no_show,
            dpi=args.dpi,
            output_file=output_file,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating event log timeline: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    if fig is None:
        print("No event log timeline was generated. Check filters and timestamps.",
              file=sys.stderr)
        return 1

    if output_file:
        print(f"Saved event log timeline to {output_file}")
    print("Successfully generated event log timeline.")
    return 0


def _run_promtest(args):
    """Handle --promtest mode."""
    try:
        figsize = tuple(map(float, args.figsize.split(',')))
    except ValueError:
        figsize = None

    try:
        groups = parse_promtest_file(args.csv_file)
    except Exception as e:
        print(f"Error parsing promtest file: {e}", file=sys.stderr)
        return 1

    if not groups:
        print("No test groups found in the file.", file=sys.stderr)
        return 1

    try:
        results = plot_promtest(
            groups,
            figsize=figsize,
            show_plot=not args.no_show,
            output_file=os.path.join(args.output_dir, 'promtest.png') if args.output_dir else None,
            dpi=args.dpi,
        )
        print(f"Successfully visualised {len(results)} test group(s).")
        return 0
    except Exception as e:
        print(f"Error generating promtest visualisation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())