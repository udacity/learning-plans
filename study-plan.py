# coding: utf-8
import argparse
import datetime
import numpy as np
import os
import pandas as pd


class Config():
    week2days = 7
    mins2hours = 1.0/60.0
    time_format = "%Y-%m-%d:%z"

def parse_time(time_required:str):

    time_required = time_required.strip(' \t')
    tmp = time_required.split(' ')
   
    assert len(tmp) %2 == 0, print('Expected an even number of elements in the list ',tmp)
    
    time_spec = {'weeks':0, 'days':0, 'hours':0, 'mins':0}
    
    for i in range(0,len(tmp),2):
        time = int(tmp[i])
        unit = tmp[i+1]
        
        assert time >=0, print('Invalid value for time',time) 
        
        if unit in ['mins', 'minutes', 'minutes']:
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
                            time_needed[i]['days']  * expected_weekly_hours/week2days +\
                            time_needed[i]['hours'] +\
                            time_needed[i]['mins']  * mins2hours
    return hours_required
        



def build_timeline(data, lesson_duration, commitment_by_day, start_date):
    start_weekday = start_date.weekday()
    while not commitment_by_day[start_weekday] > 0:
        start_weekday = (start_weekday+1) % Config.week2days
        start_date += 1
    
    

    lesson_timeline = []
    day_counter = 0
    cumulative_commitment = 0

    for lesson_id in range(len(lesson_duration)):
        ## Tackle lessons with duration less than one commitment-day.
        if lesson_duration[lesson_id] < commitment_by_day[start_weekday]:
            start_day_offset = day_counter
            spillover = cumulative_commitment + lesson_duration[lesson_id] - commitment_by_day

            if spillover > 0:
                end_day_offset = start_day_offset + 1
                cumulative_commitment = cumulative_commitment + lesson_duration[lesson_id] - commitment_by_day
                day_counter += 1
            else:
                end_day_offset = start_day_offset
                cumulative_commitment = cumulative_commitment + lesson_duration[lesson_id]

        ## Tackle lessons with duration exceeding one commitment-day
        else:
            ## If we have non-zero accumulated commitment-hours, skip the day
            if cumulative_commitment > 0:
                cumulative_commitment = 0
                day_counter += 1

            start_day_offset = day_counter
            ## Round up commitment-days
            end_day_offset   = start_day_offset + int(np.ceil(lesson_duration[lesson_id] / commitment_by_day)) - 1

            ## Ensure next lesson starts on next day.
            day_counter += end_day_offset-start_day_offset+1


        ## Install day info for current lesson.
        start_absolute_date = (start_date+datetime.timedelta(days=start_day_offset)).strftime('%b %d %Y')
        end_absolute_date   = (start_date+datetime.timedelta(days=end_day_offset)).strftime('%b %d %Y')
        lesson_timeline.append((data.iloc[lesson_id,1], start_absolute_date, end_absolute_date))

    return lesson_timeline
    
    


def date_to_lessons(timeline):
    mapping = dict()
    for i in range(len(timeline)):
        lesson, start_date, end_date = timeline[i]
        if mapping.get(start_date):
            mapping[start_date].append(lesson)
        else:
            mapping[start_date] = [lesson]
            
        if end_date != start_date:
            if mapping.get(end_date):
                mapping[end_date].append(lesson)
            else:
                mapping[end_date] = [lesson]
    
    ## Convert list of lessons to comma separated elements in a string
    dates = []
    lessons = []
    for key in mapping:
        dates.append(key)
        lessons.append(', '.join(mapping[key]).rstrip())
    
    date2lesson = pd.DataFrame({'Date':dates, 'Lesson':lessons})
    date2lesson.Date = pd.to_datetime(date2lesson.Date)
    date2lesson.sort_values('Date', inplace=True)
    date2lesson.Date = date2lesson.Date.dt.strftime('%b %d %Y')
    return date2lesson



def compact_date_ranges(timeline):
    dates = timeline.Date
    lessons = timeline.Lesson
    
    date_ranges = []
    lessons_ = []
    
    i = 0
    while i < len(timeline):
        if i+1 < len(timeline):
            if lessons[i] == lessons[i+1]:
                lessons_.append(lessons[i])
                date_ranges.append('-'.join([dates[i],dates[i+1]]))
                i += 2
            else:
                lessons_.append(lessons[i])
                date_ranges.append(dates[i])
                i += 1
        else:
            break
                
    return pd.DataFrame({'Dates':date_ranges, 'Lessons':lessons_})


def valid_date(s):
    try:
        date = datetime.datetime.strptime(s, Config.time_format)
    except ValueError:
        msg = f"'{s}' is not a valid date in yyyy-mm-dd:hh:mm format."
        raise argparse.ArgumentTypeError(msg)
    return date
                


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
    data = pd.read_csv(duration, header=None)
    time_requirements = list(map(parse_time, data.iloc[:,2]))

    # Sanity check learner's daily commitment.
    assert len(daily_commitment) == 1 or len(daily_commitment) == 7, ("Parameter --daily must be either a single " 
    "number for the daily commitment in hours or a list of seven numbers for each weekday's commitment.")

    # Expand short-form. 
    if len(daily_commitment) == 1:
        daily_commitment = daily_commitment * week2days

    
    lesson_durations = to_hours(time_requirements, expected_weekly_hours)
          
    timeline = build_timeline(data, lesson_durations, daily_commitment, start_date)
    
    d2l = date_to_lessons(timeline)
    
    output = compact_date_ranges(d2l)
    #print(output)
    
    os.mkdir('./plans')
    dir = os.path.dirname(os.path.abspath(duration))
    filename = os.path.basename(duration).split('.')[0]
    out_path = dir + '/' + filename + '_' + str(daily_commitment) + '.csv'
    output.to_csv(out_path, sep=',', index=False)
    print(f'File {out_path} written.')


if __name__ == '__main__':
    run()