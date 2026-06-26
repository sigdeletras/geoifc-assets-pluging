# GeoIFC Assets — Help

## What is GeoIFC Assets?

GeoIFC Assets connects QGIS vector layers with IFC building models.
It lets you select IFC properties manually and map them to GIS fields,
bridging BIM data and spatial analysis without custom scripts.

## Basic workflow

1. Open the **IFC Source** tab and select a GIS layer.
2. Click a feature in the table to load its linked IFC file.
3. Switch to **Extract & Export** to browse and select IFC properties.
4. Click **→ Load to GIS** to write the values to the active GIS feature.

---

## IFC Source tab

| Control | Description |
|---|---|
| Layer selector | Choose the GIS vector layer with IFC-linked features. |
| Refresh (↺) | Reload the layer list from the project. |
| Feature table | Lists features with their IFC file path (`ifc_source` field). |
| Open Viewer | Opens the 3D IFC viewer for the selected feature. |

> The `ifc_source` attribute must contain a valid path to a local `.ifc` file.

---

## Extract & Export tab

| Control | Description |
|---|---|
| Fields tree | IFC properties grouped by category. Check the ones you need. |
| Load template | Load a `.json` template to pre-configure field selection. |
| → Load to GIS | Write checked field values to the active GIS feature's attributes. |
| New layer | Export selected fields to a new memory layer. |
| Add to layer | Export to an existing GIS layer. |

---

## Tips

- Only features with a valid `ifc_source` path show data in the Extract tab.
- Use the **Storey** control in the viewer to filter elements by building floor.
- Templates can be shared across projects as standard JSON files.
- The plugin is compatible with QGIS 3.x and QGIS 4.x.
