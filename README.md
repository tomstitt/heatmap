# heatmap

Generating heatmap pictures from gpx data, optional strava downloader.

1. Run *download.py* to get your strava *gpx* data
2. Run *draw.py* to create some pictures


## Examples

`./draw.py cluster --activity-type 9`:
![a heatmap](images/defaults.png)

`./draw.py cluster --line-color cmap:plasma --activity-type 9 --line-alpha .5`:
![another heatmap](images/plasma.png)
