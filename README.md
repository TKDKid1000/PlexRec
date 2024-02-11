# PlexRec

Implementing the one missing feature that Plex has yet to add: a recommendation system.

## Description

This project is designed as a very crude and certainly rudimentary, yet functional implementation of an AI-based suggestion system for [Plex](https://plex.tv). This system is supposed to work separately from the main media server, and simply update a Plex playlist with your daily recommendations! It was originally thrown together in two nights because I needed shows to watch.

- Recommending items without user data collection.
- Determines suggestions through previously viewed shows.
- Simple, embedding-based suggestion algorithm.

## Usage

Coming soon.

## To Do

- [x] Add a based, embedding-based suggestion system.
- [ ] Implement more criteria for ranking, such as:
  - [ ] IMDB ratings for rankings.
  - [x] User's star reviews of past shows.
  - [ ] Currently trending shows from web searches.
  - [ ] Maybe an autonomous AI agent that can learn and create suggestions using the above.
- [ ] Store past suggestions and use that for future suggestions.
- [ ] A better way to manage the suggestions than a playlist.
- [ ] Making this system easy to deploy.
- [ ] Add some kind of UI.
- [ ] Automatically run and generate suggestions at a selected interval.
- [ ] Documentation 😳

## License

MIT, like always.
