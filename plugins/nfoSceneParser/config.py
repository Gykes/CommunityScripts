# Looks for existing studios also in aliases
nfo_path = "with files"

# filenaming options: stashid or filename?
# if you set the above to "with files", it'll force filename anyway, to match the filename.
filename = "stashid"

# Looks for existing studios also in aliases
create_missing_studio = True

# Looks for existing studios also in aliases
create_missing_performer = True

# Looks for existing studios also in aliases
create_missing_movie = True

# Looks for existing studios also in aliases
search_studio_aliases = True

# Looks for existing performers also in aliases
search_performer_aliases = True

# "Single names" means performers with only one word as name like "Anna" or "Siri".
# If true, single names aliases will be ignored => only the "main" performer name will determine 
# if a performer already exists).
# Only relevant if search_performer_aliases is True.
ignore_single_name_performer_aliases = True

# If True, will override existing data from the nfo or pattern.
# Otherwise, it will not change existing data, only add the missing fields. 
# Typically, newly created scenes are empty, but other plug-ins may have set some data already...
# Adapt according to your trust in your NFO data quality ;-)
override_values = True

# If True, will do nothing for already "organized" scenes. 
skip_organized = True

# If dry is True, will do a trial run with no permanent changes. 
dry_mode = False

# Blacklist: array of nfo fields that will not be loaded into the scene.
# Possible values are the usual scene field names: title, detail, studio, performers, tags, movie,...
# Example: blacklist = ["Tags", "Image"]
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
