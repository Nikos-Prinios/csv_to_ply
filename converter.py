import base64
import io
import os
import pandas as pd
import numpy as np
from plyfile import PlyData, PlyElement
from dash import dcc, html
import dash
from dash.dependencies import Input, Output, State
import chardet
import csv
import dash_bootstrap_components as dbc


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX], suppress_callback_exceptions=True)

app.layout = dbc.Container(
    [
        dbc.Card(
            [
                dbc.CardHeader(html.H4("CSV to PLY format", className="text-center text-light"),
                               className="bg-primary"),
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.Upload(
                                        id="upload-data",
                                        children=html.Button("Load CSV file", className="btn btn-primary"),
                                        style={
                                            "width": "100%",
                                            "height": "60px",
                                            "lineHeight": "60px",
                                            "borderWidth": "1px",
                                            "borderStyle": "dashed",
                                            "borderRadius": "5px",
                                            "textAlign": "center",
                                            "margin": "10px"
                                        },
                                        multiple=False
                                    ),
                                    width={"size": 12, "offset": 0},
                                    className="d-flex justify-content-center"
                                )
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(id="output-data-upload", className="text-center"),
                                    width={"size": 12, "offset": 0},
                                )
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.H5("Axis definition", className="text-center text-primary"),
                                    width=12,
                                )
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(id="coordinates-container", className="text-center"),
                                    width={"size": 12, "offset": 0},
                                )
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Button("Convert", id="convert-button", n_clicks=0,
                                                className="btn btn-primary mt-4"),
                                    width={"size": 12, "offset": 0},
                                    className="d-flex justify-content-center"
                                )
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(id="output-conversion", className="text-center"),
                                    width={"size": 12, "offset": 0},
                                )
                            ]
                        ),
                    ]
                ),
            ],
            className="mt-3",
            style={"max-width": "500px"},
        ),
    ],
    className="d-flex justify-content-center"
)


def generate_dropdown_options(column_names):
    options = [{"label": col, "value": col} for col in column_names]
    return options


@app.callback(
    [Output("output-data-upload", "children"),
     Output("coordinates-container", "children")],
    [Input("upload-data", "contents")],
    [State("upload-data", "filename")]
)
def parse_upload(contents, filename):
    if contents is not None:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        result = chardet.detect(decoded)
        encoding = result["encoding"]
        try:
            first_line = decoded.decode(encoding).split('\n')[0]
            delimiter = csv.Sniffer().sniff(first_line).delimiter
            df = pd.read_csv(io.StringIO(decoded.decode(encoding)), encoding=encoding, sep=delimiter)

            column_names = df.columns.tolist()

            coordinates_dropdowns = html.Div([
                dcc.Dropdown(
                    id='x-dropdown',
                    options=[{'label': i, 'value': i} for i in column_names],
                    placeholder="Column for x"
                ),
                dcc.Dropdown(
                    id='y-dropdown',
                    options=[{'label': i, 'value': i} for i in column_names],
                    placeholder="Column for y"
                ),
                dcc.Dropdown(
                    id='z-dropdown',
                    options=[{'label': i, 'value': i} for i in column_names],
                    placeholder="Column for z"
                ),
                dcc.Dropdown(
                    id='depth-dropdown',
                    options=[{'label': 'None', 'value': 'None'}] + [{'label': i, 'value': i} for i in column_names],
                    placeholder="Any Depth Column?"
                )

            ])

            return f"Fichier chargé: {filename}", coordinates_dropdowns
        except pd.errors.ParserError:
            return "Error reading file.", []

    return "", []


import re


@app.callback(
    Output("output-conversion", "children"),
    [Input("convert-button", "n_clicks")],
    [State("x-dropdown", "value"),
     State("y-dropdown", "value"),
     State("z-dropdown", "value"),
     State("depth-dropdown", "value"),
     State("upload-data", "contents"),
     State("upload-data", "filename")]
)
def convert_to_ply(n_clicks, x_column, y_column, z_column, depth_dropdown, contents, filename):
    if n_clicks > 0:
        if contents is not None:
            content_type, content_string = contents.split(",")
            decoded = base64.b64decode(content_string)
            try:
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), sep=",")

                if not df[x_column].dtype.kind in 'if' or not df[y_column].dtype.kind in 'if' or not df[
                                                                                                         z_column].dtype.kind in 'if':
                    return "Error: x, y and z columns must contain numeric data."

                attribute_columns = [col for col in df.columns if
                                     col.lower() not in [x_column.lower(), y_column.lower(), z_column.lower()]]

                depth_columns = []
                if depth_dropdown is not None:
                    selected_depth_prefix = re.match(r'^([a-zA-Z]+)', depth_dropdown).group(1)
                    depth_columns = [col for col in df.columns if col.startswith(selected_depth_prefix)]

                data = []
                for index, row in df.iterrows():
                    x = row[x_column]
                    y = row[y_column]
                    z = row[z_column]
                    attributes = [row[attr_col] for attr_col in attribute_columns if attr_col not in depth_columns]
                    if depth_columns:
                        for depth_col in depth_columns:
                            depth = float(re.search(r'\d+', depth_col).group())
                            depth_value = row[depth_col]
                            if pd.notnull(depth_value):
                                data.append((x, y, z - (depth / 100), depth_value, *attributes))
                    else:
                        data.append((x, y, z, *attributes))

                dtype = [('x', 'f4'), ('y', 'f4'), ('z', 'f4')]
                for attr_col in attribute_columns:
                    if attr_col not in depth_columns:
                        dtype.append((attr_col, 'f4'))
                if depth_columns:
                    dtype.append(('value', 'f4'))

                data_array = np.array(data, dtype=dtype)

            except Exception as e:
                return html.Div([
                    html.H5("Error when converting to PLY."),
                    html.P(f"Détails de l'erreur: {str(e)}")
                ])

            element = PlyElement.describe(data_array, 'vertex')
            ply_data = PlyData([element])

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            file_name, _ = os.path.splitext(os.path.basename(filename))
            ply_file_path = os.path.join(desktop, f"{file_name}.ply")

            ply_data.write(ply_file_path)

            return html.Div([
                html.H5("Successful conversion!"),
                html.A("Your PLY file is on your desktop.")
            ])
        else:
            return html.Div([
                html.H3("No data has been downloaded."),
            ])
    else:
        return html.Div([
            html.H5("Press the 'convert' button to start conversion."),
        ])


if __name__ == "__main__":
    app.run_server()
