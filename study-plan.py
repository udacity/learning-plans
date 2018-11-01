# coding: utf-8
import datetime
import numpy as np
import pandas as pd



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


def to_hours(time_needed, daily_commitment):
    commitment_hours = [0]*len(time_needed)
    for i in range(len(time_needed)):
        commitment_hours[i] = time_needed[i]['weeks'] * 7 * daily_commitment +\
                              time_needed[i]['days'] * daily_commitment +\
                              time_needed[i]['hours'] +\
                              time_needed[i]['mins']/60
    return commitment_hours
        



def build_timeline(data, hours_required, daily_commitment, start_date):
    lesson_timeline = []
    day_counter = 0
    cumulative_commit = 0

    for lesson_id in range(len(hours_required)):
        ## Tackle lessons with duration less than one commitment-day.
        if hours_required[lesson_id] < daily_commitment:
            start_day_offset = day_counter
            spillover = cumulative_commit + hours_required[lesson_id] - daily_commitment

            if spillover > 0:
                end_day_offset = start_day_offset + 1
                cumulative_commit = cumulative_commit + hours_required[lesson_id] - daily_commitment
                day_counter += 1
            else:
                end_day_offset = start_day_offset
                cumulative_commit = cumulative_commit + hours_required[lesson_id]

        ## Tackle lessons with duration exceeding one commitment-day
        else:
            ## If we have non-zero accumulated commitment-hours, skip the day
            if cumulative_commit > 0:
                cumulative_commit = 0
                day_counter += 1

            start_day_offset = day_counter
            ## Round up commitment-days
            end_day_offset   = start_day_offset + int(np.ceil(hours_required[lesson_id] / daily_commitment)) - 1

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
                
    return pd.DataFrame({'Dates':date_ranges, 'Lessons':lessons_})
                


def run():
    data = pd.read_csv('da.csv', header=None)
    time_requirements = list(map(parse_time, data.iloc[:,2]))

    daily_commitment = 4
    hours_required = to_hours(time_requirements, daily_commitment)
    start_date = datetime.date(2018,9,11)
    
    timeline = build_timeline(data, hours_required, daily_commitment, start_date)
    d2l = date_to_lessons(timeline)
    
    output = compact_date_ranges(d2l)
    print(output)



if __name__ == '__main__':
    run()