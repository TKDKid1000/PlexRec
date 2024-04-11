# PlexRec

Implementing the one missing feature that Plex has yet to add: a recommendation system.

## Description

This project is designed as a very crude and certainly rudimentary, yet functional implementation of an AI-based suggestion system for [Plex](https://plex.tv). This system is supposed to work separately from the main media server, and simply update a Plex playlist with your daily recommendations! It was originally thrown together in two nights because I needed shows to watch.

- Recommending items without user data collection.
- Determines suggestions through previously viewed shows.
- Simple, embedding-based suggestion algorithm.

## Usage

1. Install the app from PyPi using: `pip3 install plexrec`.
2. Create a `.env` file in the project's root directory containing `PLEX_SERVER_URL` and `PLEX_TOKEN`.
   1. Open the [Plex web app](https://app.plex.tv/desktop/#!/) in a browser with modern developer tools. This could be Chrome, Firefox, Edge, Safari, or any other that can log network requests.
   2. Open your browser's developer tools and navigate to the "Network" tab in your respective browser.
      Reload the page <kbd>Ctrl/Cmd+R</kbd>.
   3. Scroll until you find the first successful (status 200) request to `/providers`. Copy the main URL through the port number as `PLEX_SERVER_URL`, and the value of `X-Plex-Token` as `PLEX_TOKEN`.
3. Configure the relatively self-explanatory `config.yml` as you would like. Visit the documentation page on configuration for more details.
4. Execute the command `python3 -m plexrec` in the same directory as your `config.yml` and `.env` files.
5. You can now visit the recommendations UI at any time, or navigate to the "Recommendations" playlist in any Plex app. The recommendations UI is certainly easier to navigate, and it has many more features, but the playlist is there to make your recommendations accessible anywhere that you watch Plex.

## Configuration

This app has one unnecessarily long configuration file, `config.yml`, to manage (almost) the entire app's configuration. As the extension suggests, it is written in YAML, which is a pretty easy configuration language to read and edit in. Just copying the default `config.yml` should be enough for most people, but some minor changes are possible. These are the elements to focus on:

- **Server host and port (`server.host`, `server.port`):** These allow you to set, of course, the hostname and port that the Plex recommendation server runs on. Typically, these do not need to be changed, as the entire system works just fine without the UI. However, if you wanted to make the UI accessible outside of the server's network, you can simply set the `server.host` value to `0.0.0.0` instead of `127.0.0.1`, which then allows access as long as the port is forwarded on TCP.
- **Playlist prune (`playlist.prune`):** This setting is one of the more minor ones, but it can have a relatively significant impact. If this is enabled, the length of the recommendation playlist will always be set to the maximum possible recommendation results, which is currently hardcoded to 10. If you disable this, however, all of your historical recommendations will remain in the playlist until manually removed, even watched ones.
- **Added Penalty (`weighted.added_penalty`):** Introduces a penalty based on when media was added to your Plex server. Using a negative number here will make recently added media more prevalent, while using a positive number increases the likelihood of returning older media. Set it to 0 or remove it to eliminate its effect.

## To Do

- [x] Add a basic, embedding-based suggestion system.
- [ ] Implement more criteria for ranking, such as:
  - [x] IMDB ratings for rankings.
  - [x] User's star reviews of past shows.
  - [ ] Currently trending shows from web searches.
  - [ ] Maybe an autonomous AI agent that can learn and create suggestions using the above.
- [ ] Store past suggestions and use that for future suggestions.
- [ ] A better way to manage the suggestions than a playlist.
- [ ] Making this system easy to deploy.
- [x] Add some kind of UI. (If half checks were possible, they would belong here.)
- [ ] Automatically run and generate suggestions at a selected interval.
- [ ] Documentation 😳
- [ ] Enable setup through PyPi instead of cloning.
- [ ] Merge the server URL and token into the config (more of a note to self).
- [ ] Allow the usage of multiple media servers.
- [ ] Find a method of managing dynamic IP addresses that will inevitably crash the server.
- [ ] Create and/or adapt an image/video embedding model for maximum processing capabilities. OR use captions for embeddings.
- [ ] Add threshold with that checks when last watched is a long time ago, and allows that movie to be resuggested.
- [ ] Use clustering to make multiple averages instead of one, allowing multiple genres of content.
- [ ] Add a "don't like this" feature to the web UI.

## Contributing

I welcome contributions if you have any to make! Even something as simple as opening an issue helps. If you want to help by contributing code, I ask the following:

- Run your code through Pylint first to eliminate some common issues.
- Format your code using the Black formatter.

This project uses [PDM](https://github.com/pdm-project/pdm), which is basically the best package manager I have found for Python so far. Setting up this project with PDM is super easy. Just clone it and run `pdm install` in the project's root directory.

## License

MIT, like always.
