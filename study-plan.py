# coding: utf-8
import argparse
import datetime
import os
import pandas as pd

from config import Config

def parse_time(time_required:str):

    time_required = time_required.strip(' \t')
    tmp = time_required.split(' ')
   
    assert len(tmp) %2 == 0, print('Expected an even number of elements in the list ',tmp)
    
    time_spec = {'weeks':0, 'days':0, 'hours':0, 'mins':0}
    
    for i in range(0,len(tmp),2):
        time = int(tmp[i])
        unit = tmp[i+1]
        
        assert time >=0, print('Invalid value for time',time) 
        
        if unit in ['mins', 'minute', 'minutes']:
            time_spec['mins'] += time
        elif unit in ['hour', 'hours']:
            time_spec['hours'] += time
        elif unit in ['day', 'days']:
            time_spec['days'] += time
        elif unit in ['week', 'weeks']:
            time_spec['weeks'] += time
        else:
            raise ValueError('Invalid unit %s when trying to parse %s'%(unit,tmp))
            
    return time_spec 


def to_hours(time_needed, expected_weekly_hours):
    hours_required = [0]*len(time_needed)
    for i in range(len(time_needed)):
        hours_required[i] = time_needed[i]['weeks'] * expected_weekly_hours +\
                            time_needed[i]['days']  * expected_weekly_hours/Config.week2days +\
                            time_needed[i]['hours'] +\
                            time_needed[i]['mins']  * Config.mins2hours
    return hours_required
        



def build_timeline(data, lesson_duration, commitment_by_day, start_date, margin=0.25):
    nb_lesson = len(lesson_duration)

    weekday = start_date.weekday()

    commitment_info = {'date':start_date, 'nb_hours':commitment_by_day[weekday]}
    lesson_info = {'id':0, 'nb_hours':lesson_duration[0]}

    lesson_timeline = []

    def __incr_lesson__():
        lesson_info['id'] += 1
        lesson_info['nb_hours'] = lesson_duration[lesson_info['id']]\
            if lesson_info['id'] < nb_lesson else None

    def __incr_day__():
        commitment_info['date'] = commitment_info['date'] + datetime.timedelta(days=1)
        commitment_info['nb_hours'] = commitment_by_day[commitment_info['date'].weekday()]


    while lesson_info['id'] < nb_lesson:
        commitment_offered = commitment_info['nb_hours']
        commitment_required = lesson_info['nb_hours']

        if commitment_offered == 0 or commitment_offered < margin:
            __incr_day__()

        else:
            if commitment_offered >= commitment_required:
                lesson_timeline.append((commitment_info['date'], data.Lesson[lesson_info['id']]))
                __incr_lesson__()
                commitment_info['nb_hours'] = commitment_offered - commitment_required

            else:
                lesson_timeline.append((commitment_info['date'], data.Lesson[lesson_info['id']]))
                __incr_day__()
                lesson_info['nb_hours'] = commitment_required - commitment_offered


    dates, lessons = zip(*lesson_timeline)
    return pd.DataFrame(data={'Date':dates, 'Lessons':lessons})



def compact_timeline(timeline):
    
    def __collate_dates__(data):
        '''Assing group IDs to sequential dates'''
        date_group = [0] * len(data)
        
        for i in range(1,len(data)):
            if (data.Date.iloc[i] - data.Date.iloc[i-1]).days <= 1:
                date_group[i] = date_group[i-1]
            else:
                date_group[i] = date_group[i-1]+1 
        return date_group

    def __to_date_range__(data):
        start_date = data.Date.iloc[0].strftime(Config.output_time_format)
        end_date = data.Date.iloc[-1].strftime(Config.output_time_format)
        if end_date != start_date:
            return start_date + Config.date_range_separator + end_date
        
        return start_date

    def __collapse_dates__(data):
        '''Convert sequential dates to a date range string.'''
        # Convert to date ranges, wherever required
        date_groups = __collate_dates__(data) 

        # Group by date ranges, then drop group column(index).
        out = data.groupby(date_groups).apply(__to_date_range__).reset_index(drop=True)
        return out

    def __collapse_lessons__(data):
        '''Convert 1 or more lesson name strings to a list of lesson names'''
        lessons = ', '.join(list(data.Lessons))
        return lessons
        
    timeline_by_lessons = pd.DataFrame(timeline\
        .groupby(timeline.Lessons, sort=False)\
        .apply(__collapse_dates__)\
        .reset_index('Lessons'))
    
    timeline_by_lessons.columns = ['Lessons', 'Date']
    
    timeline_by_dates = pd.DataFrame(timeline_by_lessons\
        .groupby(timeline_by_lessons.Date)\
        .apply(__collapse_lessons__)\
        .reset_index('Date'))
    
    timeline_by_dates.columns = ['Date','Lessons']
    
    return timeline_by_dates
        



def valid_date(s):
    try:
        date = datetime.datetime.strptime(s, Config.input_time_format)
    except ValueError:
        msg = f"'{s}' is not a valid date in yyyy-mm-dd:hh:mm format."
        raise argparse.ArgumentTypeError(msg)
    return date


def stamp_weekday(data):
    weekday = []
    for date_range in data.Date:
        dates = date_range.split(Config.date_range_separator)
        start_date = dates[0]
        end_date   = dates[-1]

        start_weekday = datetime.datetime.strptime(start_date,Config.output_time_format).strftime('%A')
        end_weekday   = datetime.datetime.strptime(end_date,Config.output_time_format).strftime('%A')

        out = start_weekday + ', ' + start_date
        if start_date != end_date:
            end_day = end_weekday + ',' + end_date
            out += Config.date_range_separator + end_day
        
        weekday.append(out)
    data.Date = weekday

    return data

    

def run():
    parser = argparse.ArgumentParser('study-plan.py')
    parser.add_argument('--duration',type=str, help='Path to CSV file containing lesson-wise durations.')
    parser.add_argument('--expected',type=float, help='Expected commitment in hours per week.')
    parser.add_argument('--start',type=valid_date, help="Classroom open date - format YYYY-MM-DD:<UTC Offset as +/-hh:mm>.")
    parser.add_argument('--daily',type=float, nargs='+', help=("Either a single " 
    "number for the daily commitment in hours or a list of seven numbers for each weekday's commitment."))
    
    args = parser.parse_args()
    duration = args.duration
    expected_weekly_hours = args.expected
    start_date = args.start
    daily_commitment = args.daily
    
    # Read in the duration data and parse time field. 
    data = pd.read_csv(duration, header=0)
    time_requirements = list(map(parse_time, data.Duration))

    # Sanity check learner's daily commitment.
    assert len(daily_commitment) == 1 or len(daily_commitment) == 7, ("Parameter --daily must be either a single " 
    "number for the daily commitment in hours or a list of seven numbers for each weekday's commitment.")

    # If a single number is provided for commitment, expand it to a weekly list. 
    if len(daily_commitment) == 1:
        daily_commitment = daily_commitment * Config.week2days

    lesson_durations = to_hours(time_requirements, expected_weekly_hours)
    timeline = build_timeline(data, lesson_durations, daily_commitment, start_date)
    output = compact_timeline(timeline)
    output = stamp_weekday(output)
    #print(output)
    
    dir = './plans'
    if not os.path.exists(dir):
        os.mkdir(dir)
    
    filename = os.path.basename(duration).split('.')[0]
    out_path = dir + '/' + filename + '_' + str(daily_commitment) + '.csv'
    output.to_csv(out_path, sep=',', index=False)
    print(f'File {out_path} written.')


if __name__ == '__main__':
    run()