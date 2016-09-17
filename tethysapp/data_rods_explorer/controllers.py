from django.shortcuts import render
from django.http import JsonResponse
from tethys_apps.sdk.gizmos import SelectInput, MapView, MVView, DatePicker, Button, MVLayer, TimeSeries
from tethys_apps.sdk import get_spatial_dataset_engine
import os
from datetime import datetime
import zipfile
from tempfile import NamedTemporaryFile
import urllib2
from math import copysign
from model_objects import *
from utilities import get_fences
from json import dumps


def home(request):
    """
    Controller for the app 'home' page.
    """
    get_fences()
    get = request.GET
    post = request.POST
    context = initialize_model_map_context(get, post)

    return render(request, 'data_rods_explorer/app_base_dre.html', context)


def map_view(request):
    get = request.GET
    post = request.POST
    # If 'Display map' is clicked, load layers
    map_layers = load_tiff_ly(post, get)
    if map_layers:
        load_layer = map_layers[0]['options']['params']['LAYERS']
        print load_layer
    else:
        load_layer = ''

    context = {
        'load_layer': load_layer,
        'geoserver_url': GEOSERVER_URL
    }

    return JsonResponse(context)


def plot(request):
    """
    Controller for the plot page.
    """
    get = request.GET
    post = request.POST

    # Plot
    if (post and post['prevPlot'] == 'yes') or (post and post['pointLonLat'] != '-9999'):
        varname = WMS_VARS[post['model']][post['variable']][1]
        varunit = WMS_VARS[post['model']][post['variable']][2]
        pointLonLat = post['pointLonLat']
        datarod_ts = getDataRod_plot(post, pointLonLat)
        timeseries_plot = TimeSeries(
            height='250px',
            width='100%',
            engine='highcharts',
            title=False,
            y_axis_title=varname,
            y_axis_units=varunit,
            series=[{
                'name': pointLonLat,
                'data': datarod_ts
            }]
        )
        context = {'timeseries_plot': timeseries_plot}

        return render(request, 'data_rods_explorer/plot.html', context)

    else:
        model = str(get['model'].upper())
        start_date, end_date, plot_button = plot_ctrls(model, 'plot')
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'plot_button': plot_button
        }

    return render(request, 'data_rods_explorer/nav_plot.html', context)


def plot2(request):
    """
    Controller for the plot2 page.
    """
    post = request.POST
    get = request.GET

    # Plot
    if (post and post['prevPlot'] == 'yes') or (post and post['pointLonLat'] != '-9999'):
        pointLonLat = post['pointLonLat']
        datarod_ts = getDataRod_plot2(post, pointLonLat)
        timeseries_plot = {'y1_axis_units': WMS_VARS[post['model']][post['variable']][2],
                           'y2_axis_units': WMS_VARS[post['model2']][post['variable2']][2],
                           'series': datarod_ts}
        context = {'timeseries_plot': timeseries_plot, 'plot2': True}

        return render(request, 'data_rods_explorer/plot.html', context)

    else:
        model = get['model'].upper()
        start_date, end_date, plot_button = plot_ctrls(model, 'plot2')
        select_model2 = SelectInput(display_text='',
                                    name='model2',
                                    multiple=False,
                                    original=True,
                                    options=MODEL_OPTIONS,
                                    attributes="onchange=oc_model2();"
                                    )
        # Context variables
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'plot_button': plot_button,
            'select_model2': select_model2
        }

    return render(request, 'data_rods_explorer/nav_plot2.html', context)


def years(request):
    """
    Controller for the 'years' page.
    """
    post = request.POST
    get = request.GET
    # context = initialize_model_map_context(get, post)

    # Load page parameters
    years_list = create_years_list(1979)
    select_years = SelectInput(display_text='',
                               name='years',
                               multiple=True,
                               original=False,
                               options=years_list,
                               attributes="onchange=oc_years();"
                               )

    plot_button = Button(display_text='Plot',
                         name='years',
                         style='',
                         icon='',
                         href='',
                         submit=False,
                         disabled=False,
                         attributes='onclick=createPlot(this.name);',
                         classes='')

    # Plot
    if (post and post['prevPlot'] == 'yes') or (post and post['pointLonLat'] != '-9999'):
        varname = WMS_VARS[get['model']][get['variable']][1]
        varunit = WMS_VARS[get['model']][get['variable']][2]
        pointLonLat = post['pointLonLat']
        datarod_ts = getDataRod_years(get, pointLonLat)
        timeseries_plot = TimeSeries(
            height='250px',
            width='100%',
            engine='highcharts',
            title=False,
            y_axis_title=varname,
            y_axis_units=varunit,
            series=datarod_ts
        )
    else:
        timeseries_plot = None
    # Context variables
    context = {
        'plot_button': plot_button,
        'timeseries_plot': timeseries_plot,
        'select_years': select_years
    }

    return render(request, 'data_rods_explorer/nav_years.html', context)


def create_select_model(modelname):
    """
    Function that creates the 'model selection' element
    """
    selected_model = None
    for model in MODEL_OPTIONS:
        if model[1] == modelname.lower():
            selected_model = model[0]
    select_model = SelectInput(display_text='',
                               name='model',
                               multiple=False,
                               initial=[selected_model if selected_model else None],
                               original=True,
                               options=MODEL_OPTIONS,
                               attributes="onchange=oc_model();"
                               )
    return select_model


def create_map(layers_ls, req_post):
    """
    Function that creates the 'map' element
    """
    # Center and Zoom level
    if req_post:
        center = [round(float(req_post['centerX']), 4), round(float(req_post['centerY']), 4)]
        if req_post['zoom'] != 'undefined':
            zoom = round(float(req_post['zoom']), 2)
        else:
            zoom = 4
    else:
        center = [-96.5, 38.5]
        zoom = 4
    # Define view options
    view_options = MVView(
        projection='EPSG:4326',
        center=center,
        zoom=zoom,
        maxZoom=10,
        minZoom=3
    )
    # Define map view options
    map_view_options = MapView(
        height='500px',
        width='100%',
        controls=['ZoomSlider'],
        layers=layers_ls,
        view=view_options,
        basemap='OpenStreetMap',
        draw=True,
        legend=True)
    # Return map element
    return [MapView, map_view_options]


def map_date_ctrls(model):
    """
    Function that creates and return the "select_date", "select_hour", and "Display map" elements
    """

    select_date = DatePicker(display_text=False,
                             name='plot_date',
                             autoclose=True,
                             format='mm/dd/yyyy',
                             start_date=MODEL_FENCES[model]['start_date'],
                             end_date=MODEL_FENCES[model]['end_date'],
                             start_view=0,
                             attributes='onchange=oc_map_dt(); class=datepicker-model1',  #value=02/01/2015 'value="{0}"'.format(datetime.strftime(datetime.now() - timedelta(days=7), '%m/%d/%Y')),
                             classes=''
                             )

    select_hour = SelectInput(display_text='',
                              name='plot_hour',
                              multiple=False,
                              original=True,
                              options=[('00:00', '00'), ('01:00', '01'), ('02:00', '02'), ('03:00', '03'),
                                       ('04:00', '04'), ('05:00', '05'), ('06:00', '06'), ('07:00', '07'),
                                       ('08:00', '08'), ('09:00', '09'), ('10:00', '10'), ('11:00', '11'),
                                       ('12:00', '12'), ('13:00', '13'), ('14:00', '14'), ('15:00', '15'),
                                       ('16:00', '16'), ('17:00', '17'), ('18:00', '18'), ('19:00', '19'),
                                       ('20:00', '20'), ('21:00', '21'), ('22:00', '22'), ('23:00', '23')],
                              initial=['00:00'],
                              attributes='onchange=oc_map_dt();',
                              classes=''
                              )

    return [select_date, select_hour]


def plot_ctrls(model, controller):
    """
    Function that creates and return the "start_date", "end_hour", and "plot_button" elements
    """
    # start_date = (datetime.strptime(start_date_raw.split('T')[0], '%Y-%m-%d')-timedelta(days=1)).strftime('%m/%d/%Y')
    # end_date = (datetime.strptime(end_date_raw.split('T')[0], '%Y-%m-%d') - timedelta(days=1)).strftime('%m/%d/%Y')

    # read ascii file with output date ranges and spatial extents for all models

    differentiator = 1 if controller == 'plot' else 2

    start_date = DatePicker(display_text=False,
                            name='startDate',
                            autoclose=True,
                            format='mm/dd/yyyy',
                            start_date=MODEL_FENCES[model]['start_date'],
                            end_date=MODEL_FENCES[model]['end_date'],
                            start_view=0,
                            attributes='onchange=oc_sten_dt(); class=datepicker-model%s' % differentiator
                            )

    end_date = DatePicker(display_text=False,
                          name='endDate',
                          autoclose=True,
                          format='mm/dd/yyyy',
                          start_date=MODEL_FENCES[model]['start_date'],
                          end_date=MODEL_FENCES[model]['end_date'],
                          start_view=0,
                          attributes='onchange=oc_sten_dt(); class=datepicker-model%s' % differentiator
                          )

    plot_button = Button(display_text='Plot',
                         name=controller,
                         style='',
                         icon='',
                         href='',
                         submit=False,
                         disabled=False,
                         attributes='onclick=createPlot(this.name);',
                         classes='')

    return [start_date, end_date, plot_button]


def create_years_list(first_year=1979):
    """
    This function creates a list of tuples
    with the years available for selection
    """
    years_list = []
    last_year = datetime.now().year
    for yyyy in range(first_year, last_year + 1):
        years_list.append((str(yyyy), str(yyyy)))
    return years_list


def create_tfw_file(path, lonW, latS, lonE, latN, h=256, w=512):
    hscx = copysign((lonE - lonW)/w, 1)
    hscy = copysign((latN - latS)/h, 1)
    tfw_file = open(path, 'w')
    tfw_file.write('{0}\n'.format(hscx))
    tfw_file.write('0.0\n')
    tfw_file.write('0.0\n')
    tfw_file.write('{0}\n'.format(-hscy))
    tfw_file.write('{0}\n'.format(lonW - hscx/2, lonW))
    tfw_file.write('{0}\n'.format(latN - hscy/2, latN))
    tfw_file.write('')
    tfw_file.close()


def create_prj_file(path):
    """
    This function creates the missing .prj file for the raster
    """
    prj_file = open(path, 'w')
    prj_file.write(('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
                    'SPHEROID["WGS_1984",6378137,298.257223563]],'
                    'PRIMEM["Greenwich",0],'
                    'UNIT["Degree",0.017453292519943295]]'
                    ))
    prj_file.close()


def create_zip_file(zip_path, tiff_path, tfw_path, prj_path):
    """
    this function zips the tiff and prj files into
    """
    zip_file = zipfile.ZipFile(zip_path, "w")
    zip_file.write(tiff_path, arcname=os.path.basename(tiff_path))
    zip_file.write(tfw_path, arcname=os.path.basename(tfw_path))
    zip_file.write(prj_path, arcname=os.path.basename(prj_path))
    zip_file.close()


def get_raster_zip(latlonbox, time_st, model, variable):
    # Parameter
    lonW, latS, lonE, latN = latlonbox

    # Files, paths, and store name & store id
    tiff_file = NamedTemporaryFile(suffix=".tif", delete=False)
    tiff_path = tiff_file.name
    file_name = tiff_file.name[:-4]
    store_name = os.path.basename(file_name)
    store_id = WORKSPACE + ':' + store_name
    tfw_path = file_name + '.tfw'
    prj_path = file_name + '.prj'
    zip_path = file_name + '.zip'

    # Create tiff file
    url_image = urllib2.urlopen(DATARODS_PNG.format(lonW, latS, lonE, latN,
                                                    time_st, WMS_VARS[model][variable][0]
                                                    ))
    tiff_file.write(url_image.read())
    tiff_file.close()
    # Create prj file
    create_prj_file(prj_path)
    # Create tfw file
    create_tfw_file(tfw_path, float(lonW), float(latS), float(lonE), float(latN))
    create_zip_file(zip_path, tiff_path, tfw_path, prj_path)

    # Return
    return [zip_path, store_name, store_id]


def load_tiff_ly(req_post, req_get):
    """
    This function returns the previously loaded map or the new map layer
    if the button on the page was clicked
    """
    map_layers = []
    add_map = False
    if req_get and req_get.get('plotTime'):
        plot_time = req_get['plotTime']
    elif req_post and req_post.get('plotTime'):
        plot_time = req_post['plotTime']
    else:
        plot_time = None

    if req_get and req_get.get('model'):
        model = req_get['model']
    elif req_post and req_post.get('model'):
        model = req_post['model']
    else:
        model = None

    if req_get and req_get.get('variable'):
        variable = req_get['variable']
    elif req_post and req_post.get('variable'):
        variable = req_post['variable']
    else:
        variable = None

    if req_post and req_post['loadMap'] != 'no':
        store_id = req_post['loadMap']
        add_map = True
    elif req_get and req_get.get('loadMap') and req_get['loadMap'] != 'no':
        store_id = req_get['loadMap']
        add_map = True

    elif req_post and req_post['retrieveMap'] == 'yes':
        # Geoserver parameters
        geo_eng = get_spatial_dataset_engine(name='default')
        # Data rods parameters
        latlonbox = [req_post['lonW'], req_post['latS'],req_post['lonE'], req_post['latN']]
        time_st = plot_time + ':00:00Z/' + plot_time + ':00:30Z'
        # time_dt = datetime.strptime(plotTime, '%Y-%m-%dT%H')
        # time_st = datetime.strptime(time_dt, '%Y-%m-%dT%H:00:00Z/%Y-%m-%dT%H:00:00Z')
        # Get image from url and zip it including the .prj file
        zip_file, store_name, store_id = get_raster_zip(latlonbox, time_st, model, variable)
        # Create raster in geoserver
        response = geo_eng.create_coverage_resource(store_id=store_id,
                                                    coverage_file=zip_file,
                                                    coverage_type='worldimage',
                                                    overwrite=True,
                                                    )
        if response['success']:
            add_map = True

    if add_map == True:
        # Add raster to map
        title = '{0} {1}'.format(variable, plot_time)
        geoserver_layer = MVLayer(source='ImageWMS',
                                  options={'url': GEOSERVER_URL,
                                           'params': {'LAYERS': store_id},
                                           'serverType': 'geoserver'},
                                  legend_title=title,
                                  )
        map_layers = [geoserver_layer]

    return map_layers


def access_datarods_server(link, model, years):

    data = []
    sFile = urllib2.urlopen(link)

    if model in ['nldas', 'gldas']:
        sLines = sFile.readlines()[40:-1]
        sFile.close()

        if years:
            for row in sLines[:-1]:
                row_st = row.strip()
                data.append([datetime.strptime('2000' + row_st[4:14], '%Y-%m-%d %HZ'),
                             float(row_st[14:])
                             ])
        else:
            for row in sLines:
                row_st = row.strip()
                data.append([datetime.strptime(row_st[:14], '%Y-%m-%d %HZ'),
                             float(row_st[14:])
                             ])
    elif model in ['trmm', 'grace', 'gldas2']:
        sLines = sFile.readlines()[13:]
        sFile.close()

        if years:
            for row in sLines:
                row_ls = row.split('\t')
                data.append([datetime.strptime('2000' + row_ls[0][4:], '%Y-%m-%dT%H:%M:%S'),
                             float(row_ls[1])
                             ])
        else:
            for row in sLines:
                row_ls = row.split('\t')
                data.append([datetime.strptime(row_ls[0], '%Y-%m-%dT%H:%M:%S'),
                             float(row_ls[1])
                             ])
    return data


def getDataRod_plot(req_get, pointLonLat):
    model = req_get['model']
    variable = req_get['variable']
    if model == 'nldas':
        if variable in ["APCPsfc", "DLWRFsfc", "DSWRFsfc", "PEVAPsfc", "SPFH2m", "TMP2m", "UGRD10m", "VGRD10m"]:
            case = 'forcing'
        else:
            case = 'noah'
        superstring = DATARODS_TSB['nldas'][case]
    else:
        superstring = DATARODS_TSB[model]

    dr_link = superstring.format(variable, pointLonLat.replace(',',',%20'),
                                 req_get['startDate'], req_get['endDate'])
    dr_ts = access_datarods_server(dr_link, model, False)

    return dr_ts


def getDataRod_plot2(req_get, pointLonLat):
    startDate = req_get['startDate']
    endDate = req_get['endDate']

    # 1st variable
    model1 = req_get['model']
    variable1 = req_get['variable']

    if model1 == 'nldas':
        if variable1 in ["APCPsfc", "DLWRFsfc", "DSWRFsfc", "PEVAPsfc", "SPFH2m", "TMP2m", "UGRD10m", "VGRD10m"]:
            case1 = 'forcing'
        else:
            case1 = 'noah'
        superstring1 = DATARODS_TSB['nldas'][case1]
    else:
        superstring1 = DATARODS_TSB[model1]

    dr_link1 = superstring1.format(variable1, pointLonLat.replace(',',',%20'),
                                   startDate, endDate)
    data1 = access_datarods_server(dr_link1, model1, False)

    # 2nd variable
    model2 = req_get['model2']
    variable2 = req_get['variable2']

    if model2 == 'nldas':
        if variable2 in ["APCPsfc", "DLWRFsfc", "DSWRFsfc", "PEVAPsfc", "SPFH2m", "TMP2m", "UGRD10m", "VGRD10m"]:
            case2 = 'forcing'
        else:
            case2 = 'noah'
        superstring2 = DATARODS_TSB['nldas'][case2]
    else:
        superstring2 = DATARODS_TSB[model2]

    dr_link2 = superstring2.format(variable2, pointLonLat.replace(',',',%20'),
                                   startDate, endDate)
    data2 = access_datarods_server(dr_link2, model2, False)
    # Create list
    dr_ts = [{'name': WMS_VARS[model1][variable1][1] + ' (' + WMS_VARS[model1][variable1][2] + ')',
              'data': data1,
              'code': str(variable1) + ' (' + WMS_VARS[model1][variable1][2] + ')'},
             {'name': WMS_VARS[model2][variable2][1] + ' (' + WMS_VARS[model2][variable2][2] + ')',
              'data': data2,
              'code': str(variable2) + ' (' + WMS_VARS[model2][variable2][2] + ')'}]
    return dr_ts


def getDataRod_years(req_get, pointLonLat):
    variable = req_get['variable']
    model = req_get['model']
    if model == 'nldas':
        if variable in ["APCPsfc", "DLWRFsfc", "DSWRFsfc", "PEVAPsfc", "SPFH2m", "TMP2m", "UGRD10m", "VGRD10m"]:
            case = 'forcing'
        else:
            case = 'noah'
        superstring = DATARODS_TSB['nldas'][case]
    else:
        superstring = DATARODS_TSB[model]

    dr_ts = []
    for year in req_get['years'].split(','):
        if '-' in year:
            yearRange = year.split('-')
            for yyyy in range(int(yearRange[0]), int(yearRange[1]) + 1):
                dr_link = superstring.format(variable, pointLonLat.replace(',',',%20'),
                                             '{0}-01-01T00'.format(yyyy),
                                             '{0}-12-31T23'.format(yyyy))
                data = access_datarods_server(dr_link, model, True)
                dr_ts.append({'name': yyyy,
                              'data': data})
        else:
            dr_link = superstring.format(variable, pointLonLat.replace(',',',%20'),
                                         '{0}-01-01T00'.format(year),
                                         '{0}-12-31T23'.format(year))

            data = access_datarods_server(dr_link, model, True)
            dr_ts.append({'name': year,
                          'data': data})
    return dr_ts


def initialize_model_map_context(get, post):
    # Load model selection, map date and hour, and display map button

    if get and get.get('model'):
        model = get['model'].upper()
    elif post and post.get('model'):
        model = post['model'].upper()
    else:
        model = 'NLDAS'

    select_model = create_select_model(model)
    select_date, select_hour = map_date_ctrls(model)

    # If 'Display map' is clicked, load layers
    map_layers = load_tiff_ly(post, get)
    if map_layers:
        load_layer = map_layers[0]['options']['params']['LAYERS']
    else:
        load_layer = ''

    # Load map
    MapView, map_view_options = create_map(map_layers, post)

    context = {'select_model': select_model, 'MapView': MapView, 'map_view_options': map_view_options,
               'select_date': select_date, 'select_hour': select_hour, 'map_layers': map_layers,
               'load_layer': load_layer, 'MODEL_FENCES': dumps(MODEL_FENCES)
               }

    return context


'''
                    [{'name': 'Winter 2007-2008',
                     'data': [
                        [datetime(2008, 12, 2), 0.8],
                        [datetime(2008, 12, 9), 0.6],
                        [datetime(2008, 12, 16), 0.6],
                        [datetime(2008, 12, 28), 0.67],
                        [datetime(2009, 1, 1), 0.81]
                        ]},
                    {'name': 'Winter 2010-2011',
                     'data': [
                        [datetime(2008, 12, 2), 10.8],
                        [datetime(2008, 12, 9), 10.6],
                        [datetime(2008, 12, 16), 10.6],
                        [datetime(2008, 12, 28), 10.67],
                        [datetime(2009, 1, 1), 10.81]
                        ]}
                    ]
'''
