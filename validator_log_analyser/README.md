# Rippled Log Parser

This Python script parses and analyzes `rippled` log files to extract valuable performance and consensus metrics. It processes log entries related to ledger building, consensus advancement, and UNL validations to generate a comprehensive statistical report.

## Key Features

- **Ledger Timing Analysis**: Calculates the time taken for each ledger to close and the latency between a ledger being built and officially validated.
- **Validator Performance**: Tracks validations from each validator in the Unique Node List (UNL), measuring their individual latency relative to the consensus time.
- **Gap Detection**: Identifies and reports any skipped ledger sequences in the log file.
- **Threshold-based Alerting**: Flags ledgers whose closing time exceeds a user-defined threshold.
- **Statistical Reporting**: Generates a detailed JSON report with statistics such as mean, median, and standard deviation for ledger close times and validation latencies.
- **Raw Data Export**: Optionally outputs the full parsed ledger data in JSON format for further analysis.

## Prerequisites

- Python 3

- A `rippled` log file with specific components set to the required log levels. For the script to function correctly, you must have the following in your `rippled.cfg`:

    ```ini
    [rpc_startup]

    { "command": "log_level", "partition": "NetworkOPs", "severity": "debug" }
    { "command": "log_level", "partition": "LedgerConsensus", "severity": "debug" }
    { "command": "log_level", "partition": "LedgerMaster", "severity": "info" }
    ```

## Installation

1. **Clone the Repository or Download the Script**

2. **Install Dependencies**

    You can install the required Python libraries using `pip` and the provided `requirements.txt` file.
    
    Run the following command:

    ```bash
    pip install -r requirements.txt
    ```

    Alternatively, you can install the library manually:

    ```bash
    pip install python-dateutil
    ```

## Usage

The script is run from the command line and accepts several arguments to control its behavior.

### Command-Line Arguments

| Argument | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `file` | | **(Required)** The path to the `rippled` log file you want to analyze. | N/A |
| `--output <filename>` | `-o` | The file where the final JSON report will be saved. | `stdout` |
| `--threshold <seconds>` | `-t` | The time in seconds. Ledger closes that take longer than this value will be individually listed in the report. | `10.0` |
| `--raw-output <file>` | `-R` | An optional file path to save the complete, unprocessed JSON data for every ledger parsed. | `""` |
| `--report <boolean>` | `-r` | A flag to determine if the summary report should be generated. | `True` |

### Examples

**1. Basic Analysis**
Read a log file named `debug.log` and print the JSON summary report to the console.

```bash
python3 rippled_log_parser.py debug.log
```

**2. Writing to a File**
Analyze `debug.log` and write the summary report to `report.json`.

```bash
python3 rippled_log_parser.py debug.log -o report.json
```

**3. Custom Threshold and Raw Data Export**
Analyze `debug.log`, save the summary report to `report.json` and the raw parsed data to `raw_data.json`.

```bash
python3 rippled_log_parser.py debug.log -o report.json  -R raw_data.json
```

## Understanding the Output

The script can produce two types of output: a summarized JSON report and a raw JSON data file.

### Summary Report (`--output`)

This is the primary output, providing a high-level statistical summary of the log file analysis.

#### General Ledger Statistics

The report begins with an overview of ledger activity during the log period.

- **`start_date` / `end_date` / `duration`**: These fields show the timestamps from the first and last validated ledgers found in the log file and the total time duration between them.
- **`duration_seconds`**: The total duration expressed in seconds.
- **`ledgers`**: The total count of ledgers successfully parsed from the log file.
- **`ledger_time`**: An object containing statistics on the time interval *between* each consecutive ledger validation.
- **`gaps_total`**: The total count of "skipped" ledgers. A ledger is counted as skipped if the node did not validate it through the normal, healthy process of building it from transactions and validations. This can happen if a node acquires a ledger after it's been validated or fails to acquire it at all.
- **`gaps`**: A list of all skipped ledger ranges, detailing the start and end sequence numbers for each gap.
- **`over_threshold_total` & `over_threshold`**: A count and list of ledgers whose validation took longer than the specified `--threshold`. Each is listed with its sequence number and the duration since the previous ledger.

#### UNL Validation Statistics

This section focuses on the performance of UNL validators, starting with a network-wide summary and followed by a per-validator breakdown.

- **`valiadations` (Summary Object):**

  - `validators_total`: The total number of unique UNL validators observed.
  - `validations_total`: The total number of trusted validations received for all locally validated ledgers.
  - `validations_missed`: The total count of validations that were *not* received from a trusted validator for a given ledger.
  - `validations_late`: The quantity of validations that arrived *after* your node had already validated the ledger.
  - `validations_mean` / `median` / `stdev`: Statistical analysis of validation latency, calculated relative to your node's validation time (a negative value means the validation arrived late).

- **`validators` (Per-Validator Array):**

  - Following the summary, this array contains an object for each individual validator, describing their specific behavior using the same metrics: total validations, missed count, late count, and personal latency statistics.

#### Sample Report

```json
{
  "start_date": "2025-06-30 00:00:05.390898+00:00",
  "end_date": "2025-06-30 10:29:23.047623+00:00",
  "duration": "10:29:17.656725",
  "duration_seconds": 37757.656725,
  "ledgers": 9677,
  "gaps_total": 1,
  "gaps": [
    {
      "start": 97146623,
      "end": 97146626,
      "timestamp": "2025-06-30 01:33:38.728150+00:00"
    }
  ],
  "over_threshold_total": 0,
  "over_threshold": [],
  "ledger_time": {
    "mean": 3.902196850447479,
    "median": 3.8921170234680176,
    "stdev": 0.4848956994658969
  },
  "valiadations": {
    "validators_total": 35,
    "validations_total": 338382,
    "validations_missed": 313,
    "validations_late": 69232,
    "validations_mean": 0.31655304216143204,
    "validations_median": 0.3104,
    "validations_stdev": 0.3291009416366537
  },
  "validators": [
    {
      "master_key": "nHU2k8Po4dgygiQUG8wAADMk9RqkrActeKwsaC9MdtJ9KBvcpVji",
      "validations_total": 9676,
      "validations_missed": 1,
      "validations_late": 1992,
      "validations_mean": 0.3281560208309219,
      "validations_median": 0.3138,
      "validations_stdev": 0.3257843897835014
    }
  ]
}
```

### Raw Data Output (`--raw-output`)

If you specify a file using the `-R` flag, the script will generate a single JSON file containing an array of objects. Each object represents a single validated ledger and is useful for in-depth, ledger-by-ledger analysis.

#### Structure of a Ledger Object

- `seq`: The ledger sequence number.
- `hash`: The unique hash of this ledger.
- `timestamp`: The precise timestamp (ISO 8601) when this node advanced its consensus to this ledger. This serves as the baseline for calculating validation latencies.
- `latency`: The time in seconds that has passed since the validation of the *previous* ledger.
- `built_latency`: The time in seconds it took the node to build and accept the ledger locally after consensus was reached.
- `validations`: An object containing the timing data for each trusted validation received for this ledger.
- `peer_validations`: An object indicating whether a trusted validation was received directly from a peer.

#### The `validations` Object Explained

This object maps a validator's master public key to a numeric value representing its latency relative to your node's `timestamp`.

- A **positive value** means the validation arrived **before** your node validated the ledger (e.g., `0.75` means it arrived 0.75s early).
- A **negative value** means the validation arrived **after** your node validated the ledger (e.g., `-0.0291` means it was 29.1ms late).
- A **`null` value** means your node did not receive a validation from that validator for this ledger.

Since consensus requires \~80% of validators to agree, it is normal to see about 20% of validations arriving with negative (late) values.
