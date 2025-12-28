from pygeomag import GeoMag
import os
import datetime, time
import re
from typing import Tuple, Optional
import xml.etree.ElementTree as ET

wmm_relative_path = 'WorldMagneticModel/WMM.COF'
geo_mag = GeoMag(coefficients_file=os.getcwd()+'/'+wmm_relative_path)


def to_year_fraction(date):
    def since_epoch(epoch_date): # returns seconds since epoch
        return time.mktime(epoch_date.timetuple())
    s = since_epoch

    year = date.year
    startOfThisYear = datetime.datetime(year=year, month=1, day=1)
    startOfNextYear = datetime.datetime(year=year+1, month=1, day=1)

    yearElapsed = s(date) - s(startOfThisYear)
    yearDuration = s(startOfNextYear) - s(startOfThisYear)
    fraction = yearElapsed/yearDuration

    return date.year + fraction


def parse_iso6709(coord_str: str) -> Tuple[float, float, Optional[float]]:
    """
    Parse ISO 6709 coordinate strings into decimal degrees and altitude.

    Supported formats:
    - Latitude and Longitude in Degrees: ±DD.DDDD±DDD.DDDD
    - Latitude and Longitude in Degrees and Minutes: ±DDMM.MMMM±DDDMM.MMMM
    - Latitude and Longitude in Degrees, Minutes and Seconds: ±DDMMSS.SSSS±DDDMMSS.SSSS
    - With optional altitude: ±...±...±AAA.AAA

    Returns: (latitude, longitude, altitude) where altitude is None if not provided
    """
    # Main regex pattern for ISO 6709
    pattern = r"""
        ^
        (?P<lat_sign>[+-])
        (?P<lat_deg>\d{2}(?:\.\d+)?)       # Degrees with optional decimal
        (?P<lat_min>\d{2}(?:\.\d+)?)?      # Optional minutes
        (?P<lat_sec>\d{2}(?:\.\d+)?)?     # Optional seconds
        (?P<lon_sign>[+-])
        (?P<lon_deg>\d{3}(?:\.\d+)?)      # Degrees with optional decimal
        (?P<lon_min>\d{2}(?:\.\d+)?)?     # Optional minutes
        (?P<lon_sec>\d{2}(?:\.\d+)?)?     # Optional seconds
        (?P<alt>[+-]\d+(?:\.\d+)?)?       # Optional altitude
        $
    """

    match = re.fullmatch(pattern, coord_str, re.VERBOSE)
    if not match:
        raise ValueError(f"Invalid ISO 6709 coordinate format: {coord_str}")

    # Parse latitude
    lat_sign = -1 if match.group('lat_sign') == '-' else 1
    lat_deg = float(match.group('lat_deg'))

    # Determine format based on presence of minutes/seconds
    if match.group('lat_min'):
        lat_min = float(match.group('lat_min'))
        if match.group('lat_sec'):
            lat_sec = float(match.group('lat_sec'))
            latitude = lat_sign * (lat_deg + lat_min/60 + lat_sec/3600)
        else:
            latitude = lat_sign * (lat_deg + lat_min/60)
    else:
        latitude = lat_sign * lat_deg

    # Parse longitude
    lon_sign = -1 if match.group('lon_sign') == '-' else 1
    lon_deg = float(match.group('lon_deg'))

    if match.group('lon_min'):
        lon_min = float(match.group('lon_min'))
        if match.group('lon_sec'):
            lon_sec = float(match.group('lon_sec'))
            longitude = lon_sign * (lon_deg + lon_min/60 + lon_sec/3600)
        else:
            longitude = lon_sign * (lon_deg + lon_min/60)
    else:
        longitude = lon_sign * lon_deg

    # Parse altitude if present
    altitude = float(match.group('alt')) if match.group('alt') else None

    return latitude, longitude, altitude


def get_mag_var(latitude: float, longitude: float, altitude: float) -> float:
    result = geo_mag.calculate(glat=latitude, glon=longitude, alt=altitude, time=to_year_fraction(datetime.datetime.today()))
    return result.d


def get_mag_var_for_iso6709(coord_str: str) -> float:
    lat, lon, alt = parse_iso6709(coord_str)
    alt = 0 if alt is None else alt
    magnetic_variation = get_mag_var(lat, lon, alt)
    return magnetic_variation


def modify_positions_xml(input_file):
    # Parse the XML
    tree = ET.parse(input_file)
    root = tree.getroot()

    root_positions = root.findall('Position')
    group_positions = []
    for group in root.findall('Group'):
        group_positions.extend(group.findall('Position'))
    all_positions = root_positions + group_positions

    for position in all_positions:
        position_name = position.get("Name")
        location = position.get('DefaultCenter')
        magnetic_variation = get_mag_var_for_iso6709(location) * -1
        position.set('MagneticVariation', str(round(magnetic_variation, 2)))
        position.set('Rotation', '0')

        # Write output with proper XML formatting
    tree.write(input_file,
               encoding='utf-8',
               xml_declaration=True,
               method='xml',
               short_empty_elements=True)

    print(f"Successfully updated {len(all_positions)} positions in {input_file} with magnetic variation calculated and set all rotations to have north as up")


def modify_profile_xml(input_file):
    tree = ET.parse(input_file)
    profile = tree.getroot()

    profile.set('Name', 'Custom Australia')
    profile.set('FullName', 'Custom Eurocat Australia (YMMM/YBBB)')

    version = profile.find('Version')
    version.set('UpdateURL', '')

    tree.write(input_file,
               encoding='utf-8',
               xml_declaration=True,
               method='xml',
               short_empty_elements=True)
    print(f"Successfully updated Profile in {input_file}")


def modify_colours_xml(input_file, custom_colours_file):
    colour_bands = ['R', 'G', 'B']

    colours_tree = ET.parse(input_file)
    colours_root = colours_tree.getroot()
    colours = colours_root.findall("Colour")

    custom_colours_file = ET.parse(custom_colours_file)
    custom_colours_root = custom_colours_file.getroot()
    custom_colours = custom_colours_root.findall("Colour")

    for custom_colour in custom_colours:
        custom_colour_id = custom_colour.get('id')
        for colour in colours:
            colour_id = colour.get('id')
            if colour.get('id') == custom_colour_id:
                for band in colour_bands:
                    custom_value = custom_colour.find(band)
                    current_value = colour.find(band)
                    current_value.text = custom_value.text
                break
        else:
            print(f"Warning: Color ID '{custom_colour_id}' not found in main file")

    colours_tree.write(input_file,
               encoding='utf-8',
               xml_declaration=True,
               method='xml',
               short_empty_elements=True)

    print(f"Successfully updated Colours in {input_file}")


if __name__ == '__main__':
    modify_positions_xml('Positions.xml')
    modify_profile_xml('Profile.xml')
    modify_colours_xml('Colours.xml', 'Colours-Custom.xml')