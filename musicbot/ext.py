def contains(list, filter):
    """
    if contains(myList, lambda x: x.n == 3)  # True if any element has .n==3
        # do stuff
    """
    for x in list:
        if filter(x):
            return list.index(x)
    return False


def time_to_string(seconds):
    hour = seconds // 3600
    seconds -= hour * 3600
    minutes = seconds // 60
    seconds -= minutes * 60

    if hour > 0:
        duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
    else:
        duration = "%02dm %02ds" % (minutes, seconds)
    return duration


def add_list_time(loop):
    y = 0
    for x in loop:
        y += x['duration']
    return y
