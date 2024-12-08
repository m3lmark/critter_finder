import itertools
import os
import pandas as pd
import re
import requests
import sys
import threading
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from matplotlib import colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Rectangle
from mpl_toolkits.basemap import Basemap
from PIL import Image


done = False


def animate():
    """Displays a loading spinner in the console."""
    for c in itertools.cycle(["|", "/", "-", "\\"]):
        if done:
            break
        sys.stdout.write(f"\rloading {c}")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\rDone!          \n")


def get_inaturalist_observations(taxon_id, per_page):
    """Fetch iNaturalist observations with valid photos and coordinates."""
    observations = {}
    url = "https://api.inaturalist.org/v1/observations"
    two_days_ago = (datetime.today() - relativedelta(days=2)).strftime("%Y-%m-%d")
    params = {
        "taxon_id": taxon_id,
        "per_page": per_page,
        "has[]": ["photos", "geo"],
        "d2": two_days_ago,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        observation_response = response.json()["results"]

        for observation in observation_response:
            observation_id = observation["id"]
            observation_datetime = observation["time_observed_at"]

            if observation_datetime and datetime.fromisoformat(
                observation_datetime
            ).replace(tzinfo=None) < datetime.today() - relativedelta(days=2):
                place_guess = observation.get("place_guess", "")
                zip_code_match = re.search(r"\b\d{5}(?:[-\s]?\d{4})?\b", place_guess)
                if zip_code_match:
                    observation_data = {
                        "datetime": observation["time_observed_at"],
                        "species": observation["species_guess"],
                        "zip_code": zip_code_match.group(),
                        "coordinates": observation["location"],
                        "photo_url": observation["observation_photos"][0]["photo"][
                            "url"
                        ],
                    }
                    observations[observation_id] = observation_data
    except requests.RequestException as e:
        print(f"Error fetching iNaturalist data: {e}")
    return observations


def download_image(photo_url, obs_id):
    """Download image for the observation and save locally."""
    try:
        response = requests.get(photo_url, stream=True)
        response.raise_for_status()

        img_path = f"{obs_id}.jpg"
        with open(img_path, "wb") as img_file:
            for chunk in response.iter_content(1024):
                img_file.write(chunk)
        return img_path
    except requests.RequestException as e:
        print(f"Error downloading image for observation {obs_id}: {e}")
    return None


def plot_observations_on_map(observations):
    """Plot observations on a map with a compact legend."""
    fig, ax = plt.subplots(figsize=(12, 10))

    lats = [float(obs["coordinates"].split(",")[0]) for obs in observations.values()]
    lons = [float(obs["coordinates"].split(",")[1]) for obs in observations.values()]

    padding_factor = 0.25
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    lat_diff = max_lat - min_lat or 0.1
    lon_diff = max_lon - min_lon or 0.1

    llcrnrlat = min_lat - lat_diff * padding_factor
    urcrnrlat = max_lat + lat_diff * padding_factor
    llcrnrlon = min_lon - lon_diff * padding_factor * 4
    urcrnrlon = max_lon + lon_diff * padding_factor * 4

    m = Basemap(
        projection="merc",
        llcrnrlat=llcrnrlat,
        urcrnrlat=urcrnrlat,
        llcrnrlon=llcrnrlon,
        urcrnrlon=urcrnrlon,
        resolution="i",
        ax=ax,
    )

    m.drawcoastlines()
    m.drawstates()
    m.drawcountries()
    m.fillcontinents(color="lightgreen", lake_color="lightblue")
    m.drawmapboundary(fill_color="lightblue")
    m.drawrivers(color="blue")

    species_names = list(set(obs["species"] for obs in observations.values()))
    color_map = {
        species: color for species, color in zip(species_names, mcolors.TABLEAU_COLORS)
    }

    for obs_id, obs in observations.items():
        lat, lon = map(float, obs["coordinates"].split(","))
        x, y = m(lon, lat)

        img_path = download_image(obs["photo_url"], obs_id)
        if img_path:
            img = Image.open(img_path)
            img.thumbnail((50, 50), Image.Resampling.LANCZOS)

            border_color = color_map[obs["species"]]
            imbox = OffsetImage(img, zoom=0.5)
            ab = AnnotationBbox(
                imbox,
                (x, y),
                frameon=True,
                bboxprops=dict(edgecolor=border_color, linewidth=4),
            )
            ax.add_artist(ab)

            os.remove(img_path)

    num_species = len(color_map)
    legend_box_height = num_species * 0.1
    legend_box_width = 0.2

    legend_ax = fig.add_axes([0.05, 0.05, legend_box_width, legend_box_height])
    legend_ax.axis("off")
    legend_ax.add_patch(plt.Rectangle((0, 0), 1, 1, color="white", ec="black", lw=1))
    legend_ax.text(
        0.5, 0.95, "LEGEND", fontsize=10, weight="bold", ha="center", va="center"
    )

    for i, (species, color) in enumerate(color_map.items()):
        legend_ax.text(
            0.05,
            0.9 - i * 0.1,
            species,
            color=color,
            fontsize=8,
            weight="bold",
            ha="left",
            va="center",
        )

    return fig, ax


def plot_weather_data(observations, ax):
    """Plot weather data for each species."""
    observations = {k: v for k, v in observations.items() if v["species"]}

    species_weather = {}
    for obs_id, obs in observations.items():
        species = obs["species"]
        weather = obs.get("weather")
        if weather:
            avg_temp = weather.get("avg_temp", 0)
            rain = weather.get("rain", 0)
            species_weather.setdefault(species, {"avg_temp": [], "rain": []})
            species_weather[species]["avg_temp"].append(avg_temp)
            species_weather[species]["rain"].append(rain)

    species_weather = {
        species: data
        for species, data in species_weather.items()
        if species and data["avg_temp"] and data["rain"]
    }

    aggregated_data = [
        {
            "species": species,
            "avg_temp": int(sum(data["avg_temp"]) / len(data["avg_temp"])),
            "rain": sum(data["rain"]),
        }
        for species, data in species_weather.items()
    ]

    df_weather = pd.DataFrame(aggregated_data).dropna(subset=["avg_temp", "rain"])
    print(df_weather)

    fig, (ax_temp, ax_precip) = plt.subplots(2, 1, figsize=(10, 8))

    ax_temp.bar(df_weather["species"], df_weather["avg_temp"], color="skyblue")
    ax_temp.set_title("Average Temperature", fontsize=10)
    ax_temp.set_ylabel("Temperature (°F)", fontsize=8)
    ax_temp.set_xticks(range(len(df_weather)))
    ax_temp.set_xticklabels(df_weather["species"], rotation=45, ha="right")

    ax_precip.bar(df_weather["species"], df_weather["rain"], color="lightgreen")
    ax_precip.set_title("Total Precipitation", fontsize=10)
    ax_precip.set_ylabel("Precipitation (inches)", fontsize=8)
    ax_precip.set_xticks(range(len(df_weather)))
    ax_precip.set_xticklabels(df_weather["species"], rotation=45, ha="right")

    plt.tight_layout()
    plt.show()


def get_weather_for_observation(zip_code, date, token):
    """Fetch historical weather data for an observation."""
    url = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": token}
    params = {
        "datasetid": "GHCND",
        "datatypeid": ["TAVG", "PRCP"],
        "startdate": date,
        "enddate": date,
        "limit": 1000,
        "units": "standard",
        "location": zip_code,
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        weather = {"avg_temp": None, "rain": None}
        for record in data["results"]:
            if record["datatype"] == "TAVG":
                weather["avg_temp"] = record["value"]
            elif record["datatype"] == "PRCP":
                weather["rain"] = record["value"]
        return weather
    except requests.RequestException as e:
        print(f"Error fetching NOAA data: {e}")
    return None


def main():
    token = "replace_with_noaa_api_key"
    try:
        taxon_id = int(input("What is the ID of the taxon you would like to find?\t"))
        num_of_results = int(input("How many do you want to search through?\t\t\t"))
    except ValueError:
        print("Invalid input. Please enter numeric values.")
        exit()

    t = threading.Thread(target=animate, daemon=True)
    t.start()

    observations = get_inaturalist_observations(taxon_id, num_of_results)
    if not observations:
        print("No observations found.")
        return

    for observation in observations.values():
        observation["weather"] = get_weather_for_observation(
            observation["zip_code"], observation["datetime"].split("T")[0], token
        )

    global done
    done = True
    t.join()

    fig, ax = plot_observations_on_map(observations)
    plot_weather_data(observations, ax)


if __name__ == "__main__":
    main()
