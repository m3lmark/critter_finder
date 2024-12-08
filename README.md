
# critter finder

## description

this project grabs inaturalist observations for a specific taxon id, pulls weather data for those observations, and plots the locations on a map with additional weather graphs.

## NOAA token

to get historical weather data, you'll need an api token from [NOAA](https://www.ncei.noaa.gov/cdo-web/token).

## sample input/output

### sample input

```bash
What is the ID of the taxon you would like to find?     629866
How many do you want to search through?                 100
```

### sample output

```bash
loading /
Done!
                       species  avg_temp  rain
0         Button's Banana Slug        35  1.58
1          Slender Banana Slug        15  0.04
2                 Banana Slugs        85  0.00
3  Yellow-bordered Taildropper        33  0.01
```
![alt text](https://github.com/m3lmark/critter_finder/blob/main/critter_output.JPG?raw=true)
