# oscar_data
A curated dataset of Academy Award nominations with IMDb unique identifiers.

## Main Data File

[`oscars.csv`](oscars.csv)

### Field Guide
 * `Ceremony` (int) - Ordinal for which ceremony the nomination was for (starting at 1)
 * `Year` (string) - Year(s) from which the films are honored.
 * `Class` (string) - A custom broad grouping for categories. Values include:
   * Title (e.g. Best Picture)
   * Acting
   * Directing
   * Writing
   * Music
   * Production
   * SciTech
   * Special
 * `Canonical Category` (string) - Removes the variations on the exact wording of the category name over the years
 * `Category` (string) - The precise category name according to Oscars.org
 * `NomId` (uuid) - Unique string representing the IMDb Nomination ID
 * `Film` (string) - The title of the film (optional)
 * `FilmId` (uuid) - Unique string representing the IMDb Title ID.
 * `Name` (string) - The precise text used for who is being nominated.
 * `Nominee(s)` (comma separated strings) - The names of who is nominated in a comma separated list (without any extra text like "Written by")
 * `NomineeIds` (comma separated uuids) - Unique strings (or question marks) representing the IMDb Name ID.
 * `Winner` (bool) - True if the award was won
 * `Detail` (string) - Detail about the nomination, which could be the character name, song title, etc.
 * `Placement` (string) - In Ceremonies 6-8, the relative vote ranking was cited (e.g. came in second, tied for third, etc.) for non-winners in some categories.
 * `Note` (string) - Additional information provided about the award/nomination.
 * `Citation` (string) - Official text of the award statement, for Scientific/Technical/Honorary awards.
 * `MultifilmNomination` (bool) - Generally the data is one nomination per row, but for certain early nominations (Ceremonies 1, 2, 3 & 8), people were nominated for multiple films, and so one nomination could be spread over multiple rows.

## Generating the Data

1. Manually Download HTML
    1. Visit [The Awards Database @ Oscars.org](https://awardsdatabase.oscars.org/)
    1. Set the Award Years to the maximum possible range and Search. (Display Results by should already be set to `Category (chron)`)
    1. Save the results to `oscars_html/search_results.html`.
    1. Download the nominations by saving [The Ceremonies Page](https://www.oscars.org/oscars/ceremonies) as `oscars_html/nominations.html`
1. Prepare the Raw Oscars Data
    1. Run `./parse_oscars_html.py -n`
    1. Run `./add_fields_to_csv.py`
    1. Run `./parse_citations.py`
      * Manually update any of the citations in `citations.yaml`, and run `parse_citations.py` again as needed.
1. Obtain Lots of IMDB Data
    1. Run `./scrape_imdb_html.py`
1. Merge in IMDB Data
    1. Run `./merge.py -w`
