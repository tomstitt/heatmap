# heatmap

Generate heatmap pictures from gpx data, optional strava downloader.

1. Run *download.py* to get your strava *gpx* data
2. Run *draw.py* to create some pictures
    * You can either cluster by common location (recommended) or enter a lat-lon pair


## Examples

* `./draw.py cluster --activity-type 9`:
![a heatmap](images/defaults.png)

* `./draw.py cluster --line-color cmap:plasma --activity-type 9 --line-alpha .5`:
   * if the line color has the form `cmap:<name>` the color map name after the colon will be used with the color level determined by the altitude 
![another heatmap](images/plasma.png)
