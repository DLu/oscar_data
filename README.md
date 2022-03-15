# oscar_data
A curated dataset of Academy Award nominations with IMDb unique identifiers.

## Main Data File

[`oscars.csv`](oscars.csv)

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
