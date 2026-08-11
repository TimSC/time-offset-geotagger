# time-offset-geotagger

A small Qt/Python app for geotagging camera photos from phone GPX tracks when the camera clock is wrong.

## Workflow

1. Add one or more GPX tracks recorded by the phone.
2. Choose the photo folder.
3. Pick a calibration photo that shows the trusted phone time, or enter a manual offset.
4. Enter the actual phone date, time, timezone, and maximum GPX sample gap.
5. Preview the interpolated GPS matches.
6. Write GPS EXIF tags.

Use Clear GPS Tags to remove existing GPS EXIF data from every JPEG photo in the selected folder.

The app never changes photo timestamps. It writes GPS EXIF latitude, longitude, altitude when available, and GPS timestamp/date to JPEG photos.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Run

```bash
time-offset-geotagger
```

or:

```bash
python -m time_offset_geotagger.app
```

## Calibration

Camera EXIF times are normally stored without a timezone. The calibration step computes:

```text
offset = actual_phone_time - camera_exif_time_on_calibration_photo
```

Then each photo is matched against the loaded GPX tracks with:

```text
track_time = photo_exif_time + offset
```

The Max GPX gap setting prevents tagging across sparse sections of a track. If the surrounding GPX samples are farther apart than that threshold, the photo is left untagged in the preview.

Enter the actual phone values as separate fields:

```text
Date: 2026-07-18
Time: 14:03:22
Timezone: +01:00
```
