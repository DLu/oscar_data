# oscar_data
A curated dataset of Academy Award nominations with IMDb unique identifiers.

The unique identifiers are key to disambiguate people/films with similar names.
 * The [Kenneth Branagh](https://www.imdb.com/name/nm0000110/) who was nominated for directing *Henry V* in 1989 is the same person who was nominated for acting in a supporting role in *My Week with Marilyn* in 2011 and the same as the person who won for writing an original screenplay for *Belfast* in 2021 (as well as 5 other nominations).
 * The [Steve McQueen](https://www.imdb.com/name/nm0000537/) nominated for acting in *The Sand Pebbles* in 1966 is **not** the same as the [Steve McQueen](https://www.imdb.com/name/nm2588606) who won Best Picture for *12 Years a Slave* in 2013.
 * The most complex situation is "Robert Benton" could mean two different people, each of whom was nominated in multiple different categories.

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
 * `CanonicalCategory` (string) - Removes the variations on the exact wording of the category name over the years
 * `Category` (string) - The precise category name according to Oscars.org
 * `NomId` (uuid) - Unique string representing the IMDb Nomination ID
 * `Film` (string*) - The title of the film (optional)
 * `FilmId` (string*) - The IMDb Title ID (starting with `tt`)
 * `Name` (string) - The precise text used for who is being nominated.
 * `Nominees` (string*) - The names of who is nominated without any extra text like "Written by"
 * `NomineeIds` (string*) - IMDb Name IDs or Company IDs for nominated entities.
 * `Winner` (bool) - True if the award was won
 * `Detail` (string*) - Detail about the nomination, which could be the character name(s), song title, etc.
 * `Note` (string*) - Additional information provided about the award/nomination.
 * `Citation` (string) - Official text of the award statement, for Scientific/Technical/Honorary awards.

`*` - The fields `Film`, `FilmId`, `Nominees`, `NomineeeIds`, `Detail`, and `Note` may have multiple values if multiple entities are nominated. In these cases, the values are separated by the pipe (`|`) character.

If an IMDB identifier is unknown, it will be replaced with a question mark (`?`).

## Generating the Data

1. Manually Download HTML
    1. Visit [The Awards Database @ Oscars.org](https://awardsdatabase.oscars.org/)
    1. Set the Award Years to the maximum possible range and Search. (Display Results by should already be set to `Category (chron)`)
    1. Save the results to `oscars_html/search_results.html`.
    1. If the nominations have been announced but NOT awarded, download the nominations by saving [The Ceremonies Page](https://www.oscars.org/oscars/ceremonies) as `oscars_html/nominations.html`
1. Prepare the Raw Oscars Data
    1. Parse the HTML you just downloaded
      1. If you downloaded nomination data, run `./parse_oscars_html.py -n`
      1. Otherwise, run `./parse_oscars_html.py`
    1. Run `./add_fields_to_csv.py`
    1. Run `./parse_citations.py`
      * Manually update any of the citations in `citations.yaml`, and run `parse_citations.py` again as needed.
1. Obtain Lots of IMDB Data
    1. Run `./scrape_imdb_html.py`
1. Merge in IMDB Data
    1. Run `./merge.py -w`
