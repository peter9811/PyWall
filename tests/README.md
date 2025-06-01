# Running Tests

This directory contains unit tests for the PyWall application.

## Framework

The tests are written using Python's built-in `unittest` framework.

## How to Run Tests

To run all tests, navigate to the repository root directory in your terminal and execute the following command:

```bash
python -m unittest discover tests
```

Alternatively, you can run individual test files:

```bash
python -m unittest tests.test_config
python -m unittest tests.test_cmdWorker
```

Make sure you have any necessary dependencies installed and that the `src` directory is discoverable by Python (e.g., by setting `PYTHONPATH` or running from the root of the repository).
