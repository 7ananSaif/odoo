def safe_division(numerator, denominator, default=0):
    if denominator == 0:
        return default
    return numerator / denominator
