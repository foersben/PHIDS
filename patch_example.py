with open("tests/e2e/scenarios/test_example_scenarios.py", "r") as f:
    content = f.read()

search = """CURATED_EXAMPLE_STEMS = {
    "dry_shrubland_cycles",
    "meadow_defense",
    "mixed_forest_understory",
    "rectangular_crossfire",
    "rectangular_crossfire_extended",
    "rectangular_crossfire_enhanced",
    "root_network_alarm_chain",
    "wind_tunnel_orchard",
    "eternal_canopy_blueprint",
    "ecosystem_equilibrium_benchmark_200x200",
}"""

replace = """CURATED_EXAMPLE_STEMS = {
    "dry_shrubland_cycles",
    "meadow_defense",
    "mixed_forest_understory",
    "rectangular_crossfire",
    "rectangular_crossfire_extended",
    "rectangular_crossfire_enhanced",
    "root_network_alarm_chain",
    "wind_tunnel_orchard",
    "eternal_canopy_blueprint",
    "ecosystem_equilibrium_benchmark_200x200",
    "ecosystem_equilibrium_benchmark_256x256",
}"""

with open("tests/e2e/scenarios/test_example_scenarios.py", "w") as f:
    f.write(content.replace(search, replace))
