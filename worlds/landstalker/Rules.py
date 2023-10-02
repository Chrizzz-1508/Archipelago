from typing import Dict, List
from BaseClasses import MultiWorld, Region
from worlds.AutoWorld import LogicMixin
from worlds.landstalker.data.world_path import WORLD_PATHS_JSON


class LandstalkerLogic(LogicMixin):
    def _landstalker_has_visited_regions(self, player, regions):
        return all([self.can_reach(region, None, player) for region in regions])

    def _landstalker_has_health(self, player, health):
        return self.has("Life Stock", player, health)


def create_rules(multiworld: MultiWorld, player: int, regions_table: Dict[str, Region], dark_region_ids: List[str]):
    # Item & exploration requirements to take paths
    add_path_requirements(multiworld, player, regions_table, dark_region_ids)
    add_specific_path_requirements(multiworld, player)

    # Location rules to forbid some item types depending on location types
    add_location_rules(multiworld, player)

    # Win condition
    multiworld.completion_condition[player] = lambda state: state.has("King Nole's Treasure", player)


def add_path_requirements(multiworld: MultiWorld, player: int, regions_table: Dict[str, Region],
                          dark_region_ids: List[str]):
    can_damage_boost = multiworld.handle_damage_boosting_in_logic[player].value

    for data in WORLD_PATHS_JSON:
        name = data["fromId"] + " -> " + data["toId"]

        # Determine required items to reach this region
        required_items = data["requiredItems"] if "requiredItems" in data else []
        if "itemsPlacedWhenCrossing" in data:
            required_items += data["itemsPlacedWhenCrossing"]

        if data["toId"] in dark_region_ids:
            # Make Lantern required to reach the randomly selected dark regions
            required_items.append("Lantern")
        if can_damage_boost:
            # If damage boosting is handled in logic, remove all iron boots & fireproof requirements
            required_items = [item for item in required_items if item != "Iron Boots" and item != "Fireproof"]

        # Determine required other visited regions to reach this region
        required_region_ids = data["requiredNodes"] if "requiredNodes" in data else []
        required_regions = [regions_table[region_id] for region_id in required_region_ids]

        if not (required_items or required_regions):
            continue

        # Create the rule lambda using those requirements
        access_rule = make_path_requirement_lambda(player, required_items, required_regions)
        multiworld.get_entrance(name, player).access_rule = access_rule

        # If two-way, also apply the rule to the opposite path
        if "twoWay" in data and data["twoWay"] is True:
            reverse_name = data["toId"] + " -> " + data["fromId"]
            multiworld.get_entrance(reverse_name, player).access_rule = access_rule


def add_specific_path_requirements(multiworld: MultiWorld, player: int):
    # Make the jewels required to reach Kazalt
    jewel_count = multiworld.jewel_count[player].value
    path_to_kazalt = multiworld.get_entrance("king_nole_cave -> kazalt", player)
    if jewel_count < 6:
        # 5- jewels => the player needs to find as many uniquely named jewel items
        required_jewels = ["Red Jewel", "Purple Jewel", "Green Jewel", "Blue Jewel", "Yellow Jewel"]
        del required_jewels[jewel_count:]
        path_to_kazalt.access_rule = make_path_requirement_lambda(player, required_jewels, [])
    else:
        # 6+ jewels => the player needs to find as many "Kazalt Jewel" items
        path_to_kazalt.access_rule = lambda state: state.has("Kazalt Jewel", player, jewel_count)

    # If enemy jumping is enabled, Mir Tower sector first tree can be bypassed to reach the elevated ledge
    if multiworld.handle_enemy_jumping_in_logic[player].value == 1:
        remove_requirements_for(multiworld, "mir_tower_sector -> mir_tower_sector_tree_ledge", player)

    # Both trees in Mir Tower sector can be abused using tree cutting glitch
    if multiworld.handle_tree_cutting_glitch_in_logic[player].value == 1:
        remove_requirements_for(multiworld, "mir_tower_sector -> mir_tower_sector_tree_ledge", player)
        remove_requirements_for(multiworld, "mir_tower_sector -> mir_tower_sector_tree_coast", player)

    # If Whistle can be used from behind the trees, it adds a new path that requires the whistle as well
    if multiworld.allow_whistle_usage_behind_trees[player].value == 1:
        entrance = multiworld.get_entrance("greenmaze_post_whistle -> greenmaze_pre_whistle", player)
        entrance.access_rule = make_path_requirement_lambda(player, ["Einstein Whistle"], [])


def make_path_requirement_lambda(player, required_items, required_regions):
    """
    Lambdas are created in a for loop, so values need to be captured
    """
    return lambda state: \
        state.has_all(set(required_items), player) \
        and state._landstalker_has_visited_regions(player, required_regions)


def make_shop_location_requirement_lambda(player, location):
    """
    Lambdas are created in a for loop, so values need to be captured
    """
    # Prevent local golds in shops, as well as duplicates
    other_locations_in_shop = [loc for loc in location.parent_region.locations if loc != location]
    return lambda item: \
        item.player != player \
        or (' Gold' not in item.name
            and item.name not in [loc.item.name for loc in other_locations_in_shop if loc.item is not None])


def remove_requirements_for(multiworld: MultiWorld, entrance_name: str, player: int):
    entrance = multiworld.get_entrance(entrance_name, player)
    entrance.access_rule = lambda state: True


def add_location_rules(multiworld: MultiWorld, player: int):
    for location in multiworld.get_locations(player):
        if location.type_string == "ground":
            location.item_rule = lambda item: not (item.player == player and ' Gold' in item.name)
        elif location.type_string == "shop":
            location.item_rule = make_shop_location_requirement_lambda(player, location)

    # Add a special rule for Fahl
    fahl_location = multiworld.get_location("Mercator: Fahl's dojo challenge reward", player)
    fahl_location.access_rule = lambda state: state._landstalker_has_health(player, 15)
