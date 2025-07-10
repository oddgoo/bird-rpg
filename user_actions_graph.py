#!/usr/bin/env python
"""
User Actions Graph Generator

This script reads the nests.json file and generates a line graph showing
each user's actions over the past 30 days.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt


def load_json_data(file_path):
    """Load JSON data from the specified file path."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: File '{file_path}' contains invalid JSON.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading file: {str(e)}")
        sys.exit(1)

def extract_user_actions(data, days=40):
    """
    Extract user actions for the past specified number of days.
    Returns a dictionary mapping user IDs to a dictionary of dates and action counts.
    Default is now 90 days (approximately 3 months).
    """
    user_actions = {}
    today = datetime.now()
    
    # Create a list of dates for the past 'days' days
    date_range = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]
    
    # Initialize user_actions with zeros for all dates
    if 'daily_actions' in data:
        for user_id in data['daily_actions']:
            user_actions[user_id] = {date: 0 for date in date_range}
            
            # Fill in actual action counts where available
            for date_key in data['daily_actions'][user_id]:
                # The date_key format is "actions_YYYY-MM-DD"
                if date_key.startswith('actions_'):
                    date = date_key[8:]  # Extract the date part
                    if date in date_range:
                        actions_data = data['daily_actions'][user_id][date_key]
                        # Count the number of actions used
                        if 'used' in actions_data:
                            user_actions[user_id][date] = actions_data['used']
                        elif 'action_history' in actions_data:
                            user_actions[user_id][date] = len(actions_data['action_history'])
    
    return user_actions

def plot_user_actions(user_actions):
    """Generate a line graph of user actions over time."""
    if not user_actions:
        print("No user action data found for the specified time period.")
        return
    
    plt.figure(figsize=(12, 6))
    
    for user_id, actions in user_actions.items():
        # Sort dates chronologically
        sorted_dates = sorted(actions.keys())
        action_counts = [actions[date] for date in sorted_dates]
        
        # Plot the line for this user
        plt.plot(sorted_dates, action_counts, marker='o', linestyle='-')
    
    # Customize the plot
    plt.title('User Actions Over the Past 40 Days')
    plt.xlabel('Date')
    plt.ylabel('Number of Actions')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(True, linestyle='--', alpha=0.7)
    # Legend removed as requested
    
    # Save the plot to a file
    output_file = 'user_actions_graph.png'
    plt.savefig(output_file)
    print(f"Graph saved as '{output_file}'")
    
    # Show the plot
    plt.show()

def main():
    """Main function to run the script."""
    # Get the file path from command line arguments or use default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = 'nests.json'
    
    print(f"Loading data from '{file_path}'...")
    data = load_json_data(file_path)
    
    print("Extracting user actions...")
    user_actions = extract_user_actions(data)
    
    print("Generating graph...")
    plot_user_actions(user_actions)

if __name__ == "__main__":
    main()
