# cotd-style-bot

##### Get notified via Discord mention when a specific map style is selected for Cup of the Day. I work with all map styles! Developed for the Trackmania ice community with love <3

## Deployment Notes

This application uses [TinyDB](https://tinydb.readthedocs.io/en/latest/) for data storage, which is just a JSON file. Data is persisted by reading & writing the entire file to a free-tier Redis Cloud database on startup & shutdown. As a consequence, there can only be one instance of the app running (per environment) at any given time. Running two workers simultaneously will cause a race condition that truncates the entire database.
