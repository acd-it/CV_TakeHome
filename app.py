# ACD - OpenWeather Web Application
# This application allows users to input one or more city names,
# fetches current weather data from the OpenWeatherMap API using geocoding,
# processes the data (converting temperatures and calculates a comfort index),
# stores the results in an SQLite database, and displays the results and historical data.
#!/usr/bin/env python3
# app.py

# Import necessary libraries
import requests  # For making HTTP requests to external APIs (OpenWeatherMap)
import logging   # For logging application events and errors
import os        # For accessing environment variables (like the API key)
import sqlite3   # For interacting with the SQLite database
from flask import Flask, render_template, request, jsonify # Flask core, template rendering, request handling, JSON responses
from datetime import datetime # For timestamping database records (though CURRENT_TIMESTAMP is used in SQL)

# Configure basic logging settings
# Logs will include timestamp, log level, and the message.
# INFO level means INFO, WARNING, ERROR, and CRITICAL messages will be shown.
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize the Flask application instance
app = Flask(__name__)

# ------------------------------------------------------------------------------
# 1) Database Setup
# Functions related to initializing and interacting with the SQLite database.
# ------------------------------------------------------------------------------

def init_db():
    """
    Initializes the SQLite database.

    Connects to 'weather_data.db' (creating it if it doesn't exist).
    Creates the 'weather_records' table if it doesn't already exist,
    defining the schema for storing weather data.
    Commits the changes and closes the connection.
    Logs a confirmation message.
    """
    conn = None # Initialize connection variable
    try:
        # Connect to the SQLite database file. Creates the file if it doesn't exist.
        conn = sqlite3.connect('weather_data.db')
        cursor = conn.cursor() # Create a cursor object to execute SQL commands
        # SQL command to create the table if it doesn't exist.
        # Defines columns: id (primary key), city name, temperatures (K, C, F),
        # humidity, wind speed, weather description, comfort index, and a timestamp.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            temperature_kelvin REAL,
            temperature_celsius REAL,
            temperature_fahrenheit REAL,
            humidity INTEGER,
            wind_speed REAL,
            weather_description TEXT,
            comfort_index REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit() # Save the changes (specifically, the table creation)
        logging.info("Database initialized (table 'weather_records' ensured).")
    except sqlite3.Error as e:
        # Log any errors encountered during database initialization
        logging.error(f"Database initialization error: {e}")
    finally:
        # Ensure the database connection is closed, even if errors occurred
        if conn:
            conn.close()

def store_weather_data(weather_data_list):
    """
    Stores a list of processed weather data dictionaries into the database.

    Args:
        weather_data_list (list): A list of dictionaries, where each dictionary
                                  represents the processed weather data for one city.
                                  Expected keys are defined in the INSERT statement.
                                  Dictionaries containing an 'error' key are skipped.

    Returns:
        bool: True if storage attempt was made (even if 0 records were stored),
              False if a database or unexpected error occurred during the process.

    Connects to the database, iterates through the provided list,
    and inserts records that do not contain an 'error' key into the
    'weather_records' table. Commits all successful inserts as a single transaction.
    Logs success or failure information.
    """
    conn = None # Initialize connection variable
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('weather_data.db')
        cursor = conn.cursor() # Get a cursor object
        stored_count = 0 # Counter for successfully stored records
        # Iterate through each city's data dictionary in the input list
        for city_data in weather_data_list:
            # Only store records that do NOT have an 'error' key, indicating successful processing
            if 'error' not in city_data:
                # Execute the SQL INSERT command with parameterized query to prevent SQL injection
                cursor.execute('''
                INSERT INTO weather_records
                (city, temperature_kelvin, temperature_celsius, temperature_fahrenheit,
                 humidity, wind_speed, weather_description, comfort_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    # Provide the values corresponding to the placeholders (?)
                    city_data['city_name'],
                    city_data['temp_kelvin'],
                    city_data['temp_celsius'],
                    city_data['temp_fahrenheit'],
                    city_data['humidity'],
                    city_data['wind_speed'],
                    city_data['weather_desc'],
                    city_data['comfort_index']
                ))
                stored_count += 1 # Increment the counter for each successful insert

        conn.commit() # Commit the transaction to save all inserted records

        # Log the outcome of the storage operation
        if stored_count > 0:
            logging.info(f"Successfully stored weather data for {stored_count} locations.")
        else:
            # This case happens if the input list was empty or contained only error records
            logging.info("No new valid weather records to store.")
        return True # Indicate successful execution of the storage process

    except sqlite3.Error as e:
        # Log specific SQLite errors
        logging.error(f"Database error storing data: {e}")
        # Optionally rollback changes if needed, though commit happens only once at the end
        # if conn: conn.rollback()
        return False # Indicate failure due to database error
    except Exception as e:
        # Log any other unexpected errors
        logging.error(f"Unexpected error storing data: {e}")
        return False # Indicate failure due to unexpected error
    finally:
        # Ensure the database connection is always closed
        if conn:
            conn.close()

# ------------------------------------------------------------------------------
# 2) Weather & Geocoding Logic
# Functions related to fetching data from OpenWeatherMap (OWM) API,
# including geocoding and weather retrieval, plus data processing helpers.
# ------------------------------------------------------------------------------

# Set of recognized US state abbreviations used for geocoding fallbacks
US_STATE_ABBREVS = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
    "DC" # District of Columbia
}

# Dictionary mapping common country code synonyms to OWM-preferred codes
# Used for geocoding fallbacks (e.g., user enters "London, UK")
COUNTRY_SYNONYMS = {
    "UK": "GB" # United Kingdom -> Great Britain (as used by OWM country codes)
}

def direct_geocode(query, api_key):
    """
    Calls the OpenWeatherMap (OWM) Geocoding API (direct endpoint).

    Args:
        query (str): The location query string (e.g., "Boston, MA", "London").
        api_key (str): The OWM API key.

    Returns:
        list: A list of geocoding results (dictionaries) from the API.
              Returns an empty list ([]) if no results are found.
              Can raise requests.exceptions.RequestException on API call failure.

    Fetches coordinates and location details for the given query string.
    Uses 'limit=1' to get only the most relevant result.
    """
    # OWM Geocoding API endpoint URL
    geocode_url = "http://api.openweathermap.org/geo/1.0/direct"
    # Parameters for the API request
    geocode_params = {
        'q': query,      # The location query string
        'limit': 1,      # Limit results to the best match
        'appid': api_key # The API key for authentication
    }
    # Make the GET request to the API
    resp = requests.get(geocode_url, params=geocode_params)
    # Raise an HTTPError exception for bad status codes (4xx or 5xx)
    resp.raise_for_status()
    # Parse the JSON response and return it (expected to be a list)
    return resp.json()

def get_weather_by_latlon(lat, lon, api_key):
    """
    Fetches current weather data from OWM using latitude and longitude.

    Args:
        lat (float): Latitude.
        lon (float): Longitude.
        api_key (str): The OWM API key.

    Returns:
        dict: A dictionary containing the weather data from the OWM API.
              Can raise requests.exceptions.RequestException on API call failure.

    Uses the OWM /data/2.5/weather endpoint. 'units=standard' means temperature in Kelvin.
    """
    # OWM Current Weather API endpoint URL
    weather_url = "https://api.openweathermap.org/data/2.5/weather"
    # Parameters for the API request
    weather_params = {
        'lat': lat,        # Latitude of the location
        'lon': lon,        # Longitude of the location
        'appid': api_key,  # The API key for authentication
        'units': 'standard' # Request temperature in Kelvin (default)
    }
    # Make the GET request to the API
    weather_resp = requests.get(weather_url, params=weather_params)
    # Raise an HTTPError exception for bad status codes (4xx or 5xx)
    weather_resp.raise_for_status()
    # Parse the JSON response and return it (expected to be a dictionary)
    return weather_resp.json()

def finalize_weather_data(geocode_data, api_key):
    """
    Fetches weather data using lat/lon from geocoding results and enriches it.

    Args:
        geocode_data (list): A non-empty list containing one geocoding result dictionary
                             (as returned by direct_geocode with limit=1).
        api_key (str): The OWM API key.

    Returns:
        dict: The weather data dictionary fetched from OWM, enriched with
              'country', 'state', and 'name' fields obtained from the geocoding data.
              Returns the raw weather data if geocoding data keys are missing.
              Can raise requests.exceptions.RequestException if get_weather_by_latlon fails.

    This function bridges geocoding and weather fetching. It extracts latitude and
    longitude from the geocoding result, calls the weather API, and then injects
    the more reliable location identifiers (country, state, city name) from the
    geocoding result back into the weather data dictionary. This helps ensure
    consistent and accurate location naming.
    """
    # Extract latitude and longitude from the first (and only) geocoding result
    lat = geocode_data[0]['lat']
    lon = geocode_data[0]['lon']
    # Extract location details from geocoding result, using .get() for safety
    country_code = geocode_data[0].get('country') # e.g., "US", "GB"
    state_name = geocode_data[0].get('state')     # e.g., "Massachusetts", None if not applicable/found
    city_name = geocode_data[0].get('name')       # e.g., "Boston"

    # Fetch the weather data using the obtained latitude and longitude
    weather_data = get_weather_by_latlon(lat, lon, api_key)

    # Enrich the weather data with the location details from geocoding.
    # The weather API response might have different/missing location info,
    # so we override/add it using the more specific geocoding results.
    # Ensure the 'sys' key exists before adding country/state to it.
    if 'sys' not in weather_data:
        weather_data['sys'] = {}
    weather_data['sys']['country'] = country_code # Add/overwrite country code
    weather_data['sys']['state'] = state_name     # Add/overwrite state name
    weather_data['name'] = city_name              # Add/overwrite city name

    # Return the enriched weather data dictionary
    return weather_data

def try_geocode_fallbacks(location_query, api_key):
    """
    Attempts alternative geocoding queries if the initial direct query fails.

    Args:
        location_query (str): The original location query string from the user.
        api_key (str): The OWM API key.

    Returns:
        dict or None: An enriched weather data dictionary if a fallback query
                      successfully geocodes and fetches weather. Returns None if
                      all fallback attempts fail or result in errors.

    Implements two specific fallback strategies:
    1.  Country Synonym: If the query ends with a known synonym (like "UK"),
        replace it with the preferred code ("GB") and try geocoding again.
    2.  US State Abbreviation: If the query ends with a recognized US state
        abbreviation (like "MA"), append ", US" and try geocoding again.
    """
    # Split the query into parts based on commas, stripping whitespace
    parts = [p.strip() for p in location_query.split(",")]

    # --- Fallback (A): Country Synonym (e.g., "UK" -> "GB") ---
    # Check if the query has at least two parts (e.g., "City, Country")
    if len(parts) >= 2:
        # Get the last part (potential country code), convert to uppercase, remove periods
        last_part = parts[-1].upper().replace(".", "")
        # Check if this last part is a key in our COUNTRY_SYNONYMS dictionary
        if last_part in COUNTRY_SYNONYMS:
            # Construct the fallback query by replacing the last part with the synonym value
            fallback_query = ",".join(parts[:-1]) + f",{COUNTRY_SYNONYMS[last_part]}"
            logging.info(f"Attempting fallback for country synonym: '{location_query}' => '{fallback_query}'")
            try:
                # Attempt geocoding with the modified query
                geo_data = direct_geocode(fallback_query, api_key)
                # If the fallback geocoding returns results (is not empty)
                if geo_data:
                    # Fetch and finalize weather data using these results
                    return finalize_weather_data(geo_data, api_key)
            except requests.exceptions.RequestException as e:
                logging.warning(f"Fallback A request error for '{fallback_query}': {e}")
            except Exception as e:
                logging.warning(f"Fallback A unexpected error for '{fallback_query}': {e}")


    # --- Fallback (B): US City + State Abbreviation (e.g., "Boston, MA" -> "Boston, MA, US") ---
    # Check if the query has at least two parts (potential City, State)
    if len(parts) >= 2:
        # Get the last part (potential state abbr), uppercase, remove periods
        possible_state = parts[-1].upper().replace(".", "")
        # Check if this part is in our set of recognized US state abbreviations
        if possible_state in US_STATE_ABBREVS:
            # Construct the fallback query by appending ", US"
            fallback_query = f"{location_query}, US"
            logging.info(f"Attempting fallback by adding ', US': '{location_query}' => '{fallback_query}'")
            try:
                # Attempt geocoding with the modified query
                geo_data = direct_geocode(fallback_query, api_key)
                # If the fallback geocoding returns results
                if geo_data:
                     # Fetch and finalize weather data using these results
                    return finalize_weather_data(geo_data, api_key)
            except requests.exceptions.RequestException as e:
                logging.warning(f"Fallback B request error for '{fallback_query}': {e}")
            except Exception as e:
                logging.warning(f"Fallback B unexpected error for '{fallback_query}': {e}")

    # If neither fallback strategy yielded results, return None
    return None

def get_weather_data_geocoded(location_query, api_key):
    """
    Main function to get weather data for a location query using geocoding.

    Args:
        location_query (str): The user-provided location string.
        api_key (str): The OWM API key.

    Returns:
        dict or None: An enriched weather data dictionary if successful,
                      otherwise None if geocoding fails (even with fallbacks)
                      or if an API error occurs.

    Orchestrates the process:
    1. Tries direct geocoding on the input query.
    2. If direct fails, attempts fallback strategies via `try_geocode_fallbacks`.
    3. If any geocoding attempt succeeds, uses `finalize_weather_data` to get
       and enrich the weather data.
    4. Handles potential request errors and logs outcomes.
    """
    try:
        # --- First Attempt: Direct Geocoding ---
        logging.info(f"Attempting direct geocode for: '{location_query}'")
        geo_data = direct_geocode(location_query, api_key)
        # If direct geocoding is successful (returns a non-empty list)
        if geo_data:
            logging.info(f"Direct geocode successful for '{location_query}'. Fetching weather.")
            # Fetch and enrich weather data using the geocoding result
            return finalize_weather_data(geo_data, api_key)

        # --- Second Attempt: Fallbacks ---
        # If direct geocoding returned no results, log and try fallbacks
        logging.info(f"Direct geocode failed for '{location_query}'. Trying fallbacks...")
        weather_data = try_geocode_fallbacks(location_query, api_key)
        # If any fallback was successful and returned weather data
        if weather_data:
            logging.info(f"Fallback geocode successful for '{location_query}'.")
            return weather_data # Return the data obtained via fallback

        # --- Failure Case ---
        # If both direct and fallback geocoding failed
        logging.warning(f"All geocoding attempts failed for '{location_query}'.")
        return None # Indicate failure to find the location

    except requests.exceptions.RequestException as req_err:
        # Handle errors during the API requests (e.g., network issues, 4xx/5xx errors)
        logging.error(f"API Request error during geocoding/weather fetch for '{location_query}': {req_err}")
        return None # Indicate failure due to API error
    except Exception as e:
        # Handle any other unexpected errors during the process
        logging.error(f"Unexpected error in get_weather_data_geocoded for '{location_query}': {e}")
        return None # Indicate failure due to unexpected error

def convert_temperatures(kelvin):
    """
    Converts temperature from Kelvin to Celsius and Fahrenheit.

    Args:
        kelvin (float or None): Temperature in Kelvin.

    Returns:
        tuple: A tuple containing (celsius, fahrenheit).
               Returns (None, None) if the input kelvin is None.
    """
    if kelvin is None:
        return None, None # Handle missing input temperature
    # Formula for Kelvin to Celsius
    celsius = kelvin - 273.15
    # Formula for Celsius to Fahrenheit
    fahrenheit = (celsius * 9/5) + 32
    return celsius, fahrenheit

def calculate_comfort_index(temp_celsius, humidity, wind_speed):
    """
    Calculates a simple custom "comfort index".

    Args:
        temp_celsius (float or None): Temperature in Celsius.
        humidity (int or None): Relative humidity percentage (0-100).
        wind_speed (float or None): Wind speed (units depend on API, likely m/s).

    Returns:
        float or None: A calculated comfort index (typically between 0 and 1),
                       or None if any input parameter is None.

    This index is a simplified heuristic:
    - Normalizes temperature (Celsius, clamped 0-40), humidity (inverted, 0-100),
      and wind speed (clamped 0-10 m/s, inverted).
    - Combines them using weighted averages (50% temp, 30% humidity, 20% wind).
    - Higher values *might* indicate more "comfortable" conditions based on this specific formula.
    Note: This is a custom index and not a standard meteorological one like Heat Index or Wind Chill.
    """
    # Check if any required input is missing
    if None in [temp_celsius, humidity, wind_speed]:
        return None

    # Normalize Temperature: Clamp between 0 and 40°C, then scale to 0-1.
    # Assumes comfort decreases significantly outside this range for this simple model.
    normalized_temp = max(0, min(temp_celsius, 40)) / 40

    # Normalize Humidity: Scale 0-100 to 0-1, then invert (1 - value).
    # Assumes higher humidity is less comfortable.
    normalized_humidity = 1 - (humidity / 100)

    # Normalize Wind Speed: Clamp between 0 and 10 m/s, scale to 0-1, then invert (1 - value).
    # Assumes higher wind speed is less comfortable (up to a point).
    normalized_wind = 1 - (min(wind_speed, 10) / 10)

    # Calculate weighted average: Temperature has highest weight.
    comfort_index = 0.5 * normalized_temp + 0.3 * normalized_humidity + 0.2 * normalized_wind

    # Return the calculated index
    return comfort_index

# ------------------------------------------------------------------------------
# 3) Flask Routes
# Define the web application's endpoints (URLs) and their corresponding logic.
# ------------------------------------------------------------------------------

@app.route('/')
def index():
    """
    Handles requests to the root URL ('/').

    Returns:
        Renders the 'index.html' template, which serves as the main page
        for users to input city names.
    """
    # Renders the HTML file located in the 'templates' folder.
    return render_template('index.html')

@app.route('/get_weather', methods=['POST'])
def get_weather():
    """
    Handles POST requests to '/get_weather'.

    Expects a JSON request body containing a key 'cities' with a list of
    location query strings.
    Fetches weather data for each city using the geocoding logic.
    Processes the data, stores valid results in the database.
    Returns a JSON response containing the weather data (or errors) for each requested city.
    """
    # --- Input Validation and Setup ---
    # Get the JSON data from the incoming POST request
    data = request.get_json()
    # Basic validation: Check if data exists and has the 'cities' key
    if not data or 'cities' not in data:
        logging.warning("Received invalid request body (missing 'cities' key).")
        # Return a JSON error response with a 400 Bad Request status code
        return jsonify({'error': 'Invalid request body. "cities" key missing.'}), 400

    # Extract the list of location queries from the 'cities' key
    location_queries = data.get('cities', [])
    # Validate that 'cities' is a non-empty list
    if not isinstance(location_queries, list) or not location_queries:
        logging.warning(f"Received invalid 'cities' value: {location_queries}")
        return jsonify({'error': 'Invalid request. "cities" must be a non-empty list of strings.'}), 400

    # Retrieve the OpenWeatherMap API key from environment variables
    api_key = os.environ.get('OPENWEATHER_API_KEY')
    # Check if the API key is set
    if not api_key:
        logging.error("API Key not found. OPENWEATHER_API_KEY environment variable is not set.")
        # Return a JSON error response with a 500 Internal Server Error status code
        return jsonify({'error': 'Server configuration error (API key missing).'}), 500

    # --- Process Each Location Query ---
    all_results_data = [] # List to hold results (or errors) for each city

    # Iterate through the list of location strings provided by the user
    for location_query in location_queries:
        # Remove leading/trailing whitespace from the query
        original_input = location_query.strip()
        # Skip empty strings after stripping
        if not original_input:
            continue # Move to the next query in the list

        # Call the main function to get weather data using geocoding and fallbacks
        weather_data = get_weather_data_geocoded(original_input, api_key)

        # --- Handle Failed Fetch ---
        # If get_weather_data_geocoded returned None (failed for any reason)
        if not weather_data:
            logging.warning(f"Failed to get weather data for input: '{original_input}'")
            # Append an error dictionary to the results list for this input
            all_results_data.append({
                'original_input': original_input,
                'error': f"Could not fetch weather data for '{original_input}'. Location may be invalid, not found, or an API/network error occurred."
            })
            continue # Move to the next query

        # --- Process Successful Fetch ---
        try:
            # Extract relevant information from the returned weather_data dictionary.
            # Use .get() with default values (like {} or [{}]) to prevent KeyErrors if data is malformed.
            main_info = weather_data.get("main", {})
            temp_kelvin = main_info.get("temp")       # Temperature in Kelvin
            humidity = main_info.get("humidity")      # Humidity percentage
            weather_details = weather_data.get("weather", [{}]) # List of weather conditions (usually one)
            # Get description from the first weather condition, default to "N/A"
            weather_desc = weather_details[0].get("description", "N/A") if weather_details else "N/A"
            wind_info = weather_data.get("wind", {})
            wind_speed = wind_info.get("speed")       # Wind speed
            # Location details added during finalization step
            city_name_api = weather_data.get("name")  # City name (from geocoding)
            country_code = weather_data.get("sys", {}).get("country") # Country code (from geocoding)
            state_name = weather_data.get("sys", {}).get("state")     # State name (from geocoding, if applicable)

            # --- Data Validation ---
            # Check if essential data points were successfully extracted
            if None in [temp_kelvin, humidity, wind_speed] or not city_name_api:
                logging.warning(f"Incomplete data received from API for '{original_input}'. Raw: {weather_data}")
                all_results_data.append({
                    'original_input': original_input,
                    'city_name': city_name_api or "Unknown", # Use extracted name or default
                    'country_code': country_code,
                    'state': state_name,
                    'error': 'Incomplete data received from the weather service API.'
                })
                continue # Move to the next query

            # --- Calculate Derived Data ---
            # Convert temperature from Kelvin to Celsius and Fahrenheit
            temp_celsius, temp_fahrenheit = convert_temperatures(temp_kelvin)
            # Calculate the custom comfort index
            comfort = calculate_comfort_index(temp_celsius, humidity, wind_speed)

            # --- Format Result ---
            # Create a dictionary containing the processed data for this city
            city_result = {
                'original_input': original_input, # The user's original input string
                'city_name': city_name_api,     # Best available city name
                'country_code': country_code,   # Country code
                'state': state_name,            # State name (if available)
                'weather_desc': weather_desc,   # Weather condition description
                'temp_kelvin': temp_kelvin,     # Temp in K
                'temp_celsius': temp_celsius,   # Temp in C
                'temp_fahrenheit': temp_fahrenheit, # Temp in F
                'humidity': humidity,           # Humidity %
                'wind_speed': wind_speed,       # Wind speed (m/s likely)
                'comfort_index': comfort        # Custom comfort index
            }
            # Append the successful result to the main list
            all_results_data.append(city_result)

        except Exception as e:
            # Catch any unexpected errors during the processing of a single city's data
            logging.error(f"Error processing data for '{original_input}': {e}. Raw API Data: {weather_data}")
            # Append an error dictionary for this city
            all_results_data.append({
                'original_input': original_input,
                'error': "An internal error occurred while processing the weather data for this location."
            })
            # Continue processing the next city in the request list

    # --- Store Valid Results ---
    # Filter the results list to get only the dictionaries that represent successful fetches (no 'error' key)
    valid_records_to_store = [record for record in all_results_data if 'error' not in record]
    # If there are any valid records to store
    if valid_records_to_store:
        logging.info(f"Attempting to store {len(valid_records_to_store)} valid weather records.")
        # Call the function to store these records in the database
        store_weather_data(valid_records_to_store)
    else:
        logging.info("No valid weather records found in this batch to store in the database.")

    # --- Return Response ---
    # Return the list of all results (including errors) as a JSON response to the client
    return jsonify({'weather_data': all_results_data})

@app.route('/history')
def history():
    """
    Handles GET requests to '/history'.

    Retrieves the most recent weather records (up to 50) from the database.
    Renders the 'history.html' template, passing the retrieved records to it for display.
    """
    conn = None # Initialize connection variable
    try:
        # Connect to the database
        conn = sqlite3.connect('weather_data.db')
        # Set row_factory to sqlite3.Row to access columns by name (like dictionaries)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor() # Get a cursor object
        # Execute SQL query to select relevant columns from the weather_records table
        # Order by timestamp in descending order (most recent first)
        # Limit the results to the latest 50 entries
        cursor.execute('''
        SELECT id, city, temperature_celsius, temperature_fahrenheit, humidity,
               wind_speed, weather_description, comfort_index, timestamp
        FROM weather_records
        ORDER BY timestamp DESC
        LIMIT 50
        ''')
        # Fetch all rows returned by the query and convert each sqlite3.Row object into a standard dictionary
        records = [dict(row) for row in cursor.fetchall()]
        # Render the 'history.html' template, passing the list of record dictionaries
        return render_template('history.html', records=records)
    except Exception as e:
        # Log any errors encountered during database access or template rendering
        logging.error(f"Error retrieving or rendering history page: {e}")
        # Return a JSON error message (though ideally, an error page might be better for a GET request)
        # Or render history.html with an error message variable set.
        return jsonify({'error': f"Failed to retrieve history data: {e}"}), 500
    finally:
        # Ensure the database connection is closed
        if conn:
            conn.close()

# ------------------------------------------------------------------------------
# Main Execution Block
# This code runs only when the script is executed directly (not imported as a module).
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    # Ensure the database and table are ready before starting the app
    init_db()
    # Start the Flask development web server
    # debug=True enables auto-reloading on code changes and detailed error pages (for development only!)
    # In production, use a proper WSGI server like Gunicorn or Waitress.
    app.run(debug=True)