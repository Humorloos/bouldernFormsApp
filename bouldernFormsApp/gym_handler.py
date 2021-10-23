from functools import cached_property

import pandas as pd
from flask_restful import Resource
from matplotlib.colors import to_rgba_array

import googleApiScopes.calendar
from bouldern.color_lookup import color_lookup
from bouldern.constants import GOOGLE_API_PATH
from bouldern.gyms import gyms
from bouldern.utils import merge_back_columns, plot_gym
from bouldernFormsApp.constants import TARGET_DIR
from googleApiHelper.googleApiClientProvider import GoogleApiClientProvider

SCOPES = [googleApiScopes.calendar.CALENDAR_READ_ONLY,
          googleApiScopes.calendar.EVENTS]


class GymHandler(Resource):
    def __init__(self):
        self.gym_name = ''

    @cached_property
    def gym_data(self):
        data = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{self.gym_info["sheet_id"]}/'
                           f'export?format=csv&gid={self.gym_info["gid"]}')
        data = merge_back_columns(data, 'Unnamed', 'wall')
        data[['x', 'y']] = data.apply(
            lambda row: pd.Series(self.gym_info['sections'][row['Section']]['walls'][int(row['wall'] - 1)]), axis=1)
        return data

    @cached_property
    def gym_info(self):
        return gyms[self.gym_name]

    @staticmethod
    def get():
        return 'This page only exists to handle boulder app updates'

    def post(self):
        # invalidate gym_data cache
        self.__dict__.pop('gym_data', None)

        ax, fig = self.plot_progress()
        # Save gym sections as separate pngs
        # for some reason needs to be called before saving figures to get coordinates right
        fig.canvas.draw()
        fig.savefig(
            TARGET_DIR.joinpath(f'{self.gym_name.lower().replace(" ", "_")}.png'),
            dpi=400,
            bbox_inches=ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        )

        calendar_service = GoogleApiClientProvider(SCOPES, GOOGLE_API_PATH).get_calendar_service()
        now_timestamp = pd.Timestamp.now(tz=calendar_service.timezone)
        calendar_service.create_event(
            start=now_timestamp,
            end=now_timestamp + pd.Timedelta(minutes=30),
            summary='Bouldern Progress Update',
            color_id=color_lookup[self.gym_data['Farbe'].iloc[-1]]['calendar_id'],
            description=gyms[self.gym_name]['form_id']
        )

    def plot_progress(self):
        ax, fig = plot_gym(self.gym_name)
        boulder_colors = self.gym_data['Farbe'].apply(lambda color: color_lookup[color]['hex'])
        contrast_colors = boulder_colors.apply(
            lambda color: 'white' if to_rgba_array(color).ravel()[:3].sum() < 1 else 'black')
        gym_info = gyms[self.gym_name]
        ax.scatter(
            *self.gym_data[['x', 'y']].values.T,
            s=(gym_info['font_size']) ** 2,
            c=boulder_colors,
            marker='s',
            alpha=0.7,
            linewidths=0.8,
            edgecolors=contrast_colors,
        )
        sent_boulders = self.gym_data['Send'] == 'Yes'
        ax.scatter(
            *self.gym_data.loc[sent_boulders, ['x', 'y']].values.T,
            c=contrast_colors[sent_boulders],
            s=(gym_info['font_size'] * 0.9) ** 2,
            marker='x',
            linewidths=0.75,
        )

        return ax, fig
