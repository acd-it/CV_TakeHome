# Weather Dashboard Web Application

## Overview

The **Weather Dashboard** is a web application that allows users to fetch weather information for one or more locations. The app retrieves data such as temperature, humidity, wind speed, weather description, and a comfort index, which represents the overall comfort of a location based on weather conditions. Users can enter city names or other location identifiers, and the app will display the weather details for those locations.

The application is built using **Python** with **Flask** for the backend, and **HTML**/**Bootstrap** for the frontend. It integrates with the **OpenWeatherMap API** for geocoding and weather data retrieval.

## Features

- **Multiple Location Support**: Allows users to input multiple locations separated by semicolons (e.g., `Boston,MA; London,UK`).
- **Comfort Index**: Displays a comfort index for each location, providing a quick summary of how comfortable the weather is based on temperature, humidity, and wind speed.
- **Error Handling**: Provides clear error messages if a location is invalid or if there is an issue with fetching the weather data.
- **Historical Data Storage**: Stores weather data in an SQLite database for future reference.
- **Responsive Design**: Built with Bootstrap for a clean, responsive UI that works well on both desktop and mobile devices.

## Installation

### Prerequisites

1.  **Python 3.x**: Make sure Python 3 is installed on your machine.
2.  **OpenWeatherMap API Key**: You will need an API key from OpenWeatherMap to retrieve weather data. You can obtain one by signing up at [OpenWeatherMap](https://openweathermap.org/api).

### Setup

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd weather-dashboard
    ```

2.  Install required Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Set up the **OpenWeatherMap API Key** as an environment variable:
    ```bash
    export OPENWEATHER_API_KEY="your-api-key"
    ```
    *(On Windows, use `set OPENWEATHER_API_KEY="your-api-key"` in Command Prompt or `$env:OPENWEATHER_API_KEY="your-api-key"` in PowerShell)*

4.  Initialize the SQLite database (the application typically handles this on first run if designed to do so, or you might have a specific script):
    ```bash
    # If app.py creates the DB on startup, just running it might be enough.
    # Otherwise, you might need a command like: flask db init / flask db migrate / flask db upgrade
    # Or a custom script: python init_db.py
    # Check your specific project setup. For this example, we assume running the app handles it.
    python app.py # Run once to potentially initialize DB, then stop (Ctrl+C)
    ```

5.  Start the Flask development server:
    ```bash
    flask run
    ```
    *(Or `python app.py` if your `app.py` includes `app.run()`)*

The application should now be running at `http://127.0.0.1:5000`.

## Usage

1.  **Home Page**: The main page allows you to input one or more locations. Enter a location (e.g., `Boston,MA`) and click the "Get Weather" button to fetch weather data.
2.  **History Page**: View the last 50 records of weather data that were fetched and stored in the database.

### Example Input:

-   For US cities: `Boston,MA`
-   For international cities: `London,UK`
-   Multiple locations: `Boston,MA; London,UK`

### Output:

The app will display the following information for each location:

-   **City Name**: Location name
-   **Temperature**: Displayed in both Celsius and Fahrenheit
-   **Humidity**: Percentage
-   **Wind Speed**: In meters per second
-   **Weather Description**: General weather condition (e.g., "Clear sky")
-   **Comfort Index**: A calculated value to assess the comfort level

## Database

The application uses a **SQLite** database to store weather data. The data is stored in a table named `weather_records` with the following columns:

-   `id`: Auto-incremented record ID
-   `city`: Name of the city
-   `temperature_kelvin`: Temperature in Kelvin
-   `temperature_celsius`: Temperature in Celsius
-   `temperature_fahrenheit`: Temperature in Fahrenheit
-   `humidity`: Humidity percentage
-   `wind_speed`: Wind speed in meters per second
-   `weather_description`: Weather description (e.g., "Clear sky")
-   `comfort_index`: Calculated comfort index
-   `timestamp`: Timestamp of when the record was stored

## Error Handling

-   If a location is invalid or cannot be found, an error message will be displayed.
-   If there is an issue with the weather data retrieval (e.g., invalid API key, API service down), an appropriate error message will be shown to the user.

## Future Enhancements

If more time was available, the following features could be added:

-   **User Accounts**: Implement user accounts with login functionality to allow users to save and view their weather search history.
-   **Enhanced Comfort Index**: Add graphical representations or icons to visually indicate comfort levels (e.g., color-coding, simple icons).
-   **Caching**: Implement caching mechanisms (e.g., using Flask-Caching) to reduce the number of API calls for frequently searched locations within a short time frame.
-   **Geolocation**: Add an option to get weather for the user's current location using the browser's Geolocation API.
-   **Improved UI/UX**: Enhance the visual design and user experience further.
-   **Unit/Integration Tests**: Add comprehensive tests for backend logic and API interactions.