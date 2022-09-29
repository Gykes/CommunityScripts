# Looks for existing studios also in aliases
nfo_path = "with files"

# filenaming options: stashid or filename?
# if you set the above to "with files", it'll force filename anyway, to match the filename.
filename = "stashid"

# Creates missing entities in stash's database (or not)
create_missing_performers = True
create_missing_studio = True
create_missing_tags = True
create_missing_movie = True

# Wether to Looks for existing entries also in aliases
search_performer_aliases = True
search_studio_aliases = True

# "Single names" means performers with only one word as name like "Anna" or "Siri".
# If true, single names aliases will be ignored => only the "main" performer name will determine 
# if a performer already exists).
# Only relevant if search_performer_aliases is True.
ignore_single_name_performer_aliases = True

# If True, will do nothing for already "organized" scenes. 
skip_organized = True

# If True, will set the scene to "organized" on update from nfo file. 
set_organized_nfo = False

# If dry is True, will do a trial run with no permanent changes. 
dry_mode = False

# Blacklist: array of nfo fields that will not be loaded into the scene.
# Possible values are the usual scene field names (in lowercase): title, details, studio, performers, tags, movie,...
# Example: blacklist = ["tags", "thumbnails"]
blacklist = []

###############################################################################
# Reminder: if no matching NFO file can be found for the scene, a fallback 
# "regular expressions" based parsing is supported.
#
# ! regex patterns are defined in their own config files. 
# See README doc for details
#
# Supported names for the fallback regex capturing group:
# - studio
# - date
# - performers
# - title
# - tags
# - rating
# - movie
#
# Example regex:
# (?<studio>.*) - (?<date>.*) - (?<performers>.*)
# ^(?<studio>.*) - (?<date>.*) - (?<title>.*) - RTG\[(?<rating>.*)\]\.mp4$
###############################################################################

# Character which replaces every space in the filename
performers_splitter = ", "
