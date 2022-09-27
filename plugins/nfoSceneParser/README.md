# *nfoFileParser*
Pre-populates your scenes (during scan) based on either:
- a NFO file
- a consistent & identifiable patterns in your file names

# Installation

- Download the whole folder '**nfoFileParser**'
- Place it in your **plugins** folder (where the `config.yml` is)
- Reload plugins (Settings > Plugins > Reload)
- *nfoFileParser* appears

The plug-in is automatically triggered on each new scene creation (typically during scan)

Note: nfoFileParser works without manual config. If you want more control, have a look at `config.py`, where you can change some default behavior.

# Usage

Imports scene details from nfo files or from regex patterns.

Complies with KODI's 'Movie Template' specification (https://kodi.wiki/view/NFO_files/Templates). Note: although initially created by KODI, this NFO structure has become a de-facto standard among video management software and is used today far beyond its KODI roots to store the video files's metadata.

Every time a new scene is created (mainly you run a "scan" that finds missing scenes), it will:
  - look for a matching NFO file and parse it into the scene data (studio, performers, date, name,...)
  - if no NFO are found, it can use a fallback regex to parse the structured data directly from your scene file name. The fallback is relevant only if you have consistent & identifiable patterns in (some of) your file names. Read carefully below how to configure regex to match your file name pattern(s).
  - If none of the above is found: it will do nothing ;-)

# File organisation

The plugin automatically looks for .nfo files (and optionally thumbnail images) in the same directory and with the same filename as your video file (for instance for a `BestSceneEver.mp4` video, it will look for a corresponding `BestSceneEver.nfo` file). Though config, you can specify an alternate location for your NFO files.

Thumbnails images are either URL within the NFO itself or alternatively will be loaded from the local disk (following KODI's naming convention for movie artwork). The plug-in will use the first image it finds among:
- A download of the `thumb` field's URL (if there are multiple thumb fields in the nfo, uses the one with the "landscape" attribute has priority over "poster").
- A local image with the `-landscape` or `-landscape` suffix (example: `BestSceneEver-landscape.jpg`)

### Mapping between stash data and nfo fields

stash scene fields     | nfo movie fields
---------------------- | ---------------------
`title`                | `title` or `originaltitle` or `sorttitle`
`details`              | `plot` or `outline` or `tagline`
`studio`               | `studio`
`performers`           | `actor.name` (sorted by `actor.order`)
`movie`                | `set.name`
`rating`               | `userrating`
`tags`                 | `tag`
`cover image`          | `thumb` url (or local file)
`date`                 | `premiered` or `year`
`created at`           | `dateadded`
...

