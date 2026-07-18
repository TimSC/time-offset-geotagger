# time-offset-geotagger

A small Qt/Python app for geotagging camera photos from a phone GPX track when the camera clock is wrong.

## Workflow

1. Choose a GPX track recorded by the phone.
2. Choose the photo folder.
3. Pick a calibration photo that shows the trusted phone time, or enter a manual offset.
4. Enter the actual phone date, time, and timezone visible in that calibration photo.
5. Preview the interpolated GPS matches.
6. Write GPS EXIF tags.

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

Then each photo is matched against the GPX track with:

```text
track_time = photo_exif_time + offset
```

Enter the actual phone values as separate fields:

```text
Date: 2026-07-18
Time: 14:03:22
Timezone: +01:00
```
