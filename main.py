import generate_exposures

# future dev: make folder id a command line argument
# this should also take a list, not a single id
looker_folder_ids = 13

exposures = generate_exposures.get_dashboard_exposures(generate_exposures.get_dashboards_in_folder(looker_folder_ids))

generate_exposures.write_exposure_yaml(exposures)