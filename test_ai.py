import hashlib

def get_hash(input_string):
    # Generate a SHA-256 hash of the input string
    hash_object = hashlib.sha256(input_string.encode()).hexdigest()
    return f"Hello, your hash is {hash_object}"

# Example usage:
user_input = input("Enter a string: ")
result = get_hash(user_input)
print(result)

def calculate_taxes(employees, tax_progression):
    """
    Calculates taxes for each employee based on their salary and the given tax progression.

    :param employees: Dictionary where keys are employee names and values are their salaries.
    :param tax_progression: Dictionary where keys are income thresholds and values are corresponding tax rates.
    :return: List of tuples containing employee names and their calculated taxes.
    """

    # Calculate tax for each employee
    taxed_employees = [
        (employee, sum(
            rate * min(salary - threshold, next_threshold - salary)
            for threshold, rate in tax_progression.items() if salary >= threshold
        ))
        for employee, salary in employees.items()
    ]

    return taxed_employees

# Example usage:
employees = {
    "Alice": 50000,
    "Bob": 75000,
    "Charlie": 100000
}

tax_progression = {
    12570: 0.2,
    25040: 0.4,
    37500: 0.45,
    float('inf'): 0.48  # Top rate for higher incomes
}

taxed_employees = calculate_taxes(employees, tax_progression)
print(taxed_employees)