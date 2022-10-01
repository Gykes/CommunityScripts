# If dry is True, will do a trial run with no permanent changes. 
dry_mode = False

# nfo file location & naming.
# Possible options:
# - "with files": with the video files: Follows NFO standard naming: https://kodi.wiki/view/NFO_files/Movies
# - "...": a specific directory you mention. In this case, the nfo names will match your stash scene ids.
# if you set the above to "with files", it'll force filename anyway, to match the filename.
# ! Not yet implemented. Currently, only "with files" is supported
nfo_location = "with files"

# Creates missing entities in stash's database (or not)
create_missing_performers = True
create_missing_studio = True
create_missing_tags = True
create_missing_movie = True

# Wether to Looks for existing entries also in aliases
search_performer_aliases = True
search_studio_aliases = True

# "Single names" means performers with only one word as name like "Anna" or "Siri".
# If true, single names aliases will be ignored: 
# => only the "main" performer name determines if a performer exists or is created.
# Only relevant if search_performer_aliases is True.
ignore_single_name_performer_aliases = True

# If True, will do nothing for already "organized" scenes. 
skip_organized = True

# If True, will set the scene to "organized" on update from nfo file. 
set_organized_nfo = False

# Set of fields that must be set from the nfo (i.e. "not be empty") for the scene to be marked organized. 
# TODO: implememnt
set_organized_if = ["title", "performers", "details", "date", "studio"]

# Blacklist: array of nfo fields that will not be loaded into the scene.
# Possible values: "performers", "studio", "tags", "movie", "title", "details", "date", "rating", "director", "url" and "cover_image"
blacklist = ["rating"]

# List of tags that will never be created or set to the scene.
# Example: blacklisted_tags = ["HD", "Now in HD"]
# TODO: implememnt
blacklisted_tags = ["HD", "4K", "Now in HD"]

###############################################################################
# Reminder: if no matching NFO file can be found for the scene, a fallback 
# "regular expressions" parsing is supported.
#
# ! regex patterns are defined in their own config files. 
#
# See README.md for details
###############################################################################
