#!/usr/bin/env python3

import argparse
import dateutil.parser
import json
import re
import statistics


def timestamp_to_seconds(timestamp) -> float:
    return float("{:.4}".format(timestamp))


def parse_ledgers(filename):
    built_re = re.compile(
        r"^(.*) LedgerConsensus:DBG Built ledger #(\d+): (.*)$"
    )  # 0 1 2
    advancing_re = re.compile(
        r"^(.*) LedgerMaster:NFO Advancing accepted ledger to (\d+).*"
    )  # 0 1
    validation_re = re.compile(
        r"^(.*) NetworkOPs:DBG VALIDATION: validation:  ledger_hash: (\S+)"  # 0 1
        r" consensus_hash: (\S+)"  # 2
        r" sign_time: (.*)"  # 3
        r" seen_time: (.*)"  # 4
        r" signer_public_key: (\S+)"  # 5
        r" node_id: (\S+)"  # 6
        r" is_valid: (\d)"  # 7
        r" is_full: (\d)"  # 8
        r" is_trusted: (\d)"  # 9
        r" signing_hash: (\S+)"  # 10
        r" base58: (\S+)"  # 11
        r" master_key: (\S+)$"
    )  # 12

    # seq -> {hash, timestamp}
    builts = {}

    # seq -> timestamp
    advancings = {}

    # hash -> {seq, built_latency, hash, latency, timestamp, validations}
    ledgers_by_hash = {}

    # seq -> {seq, built_latency, hash, latency, timestamp, validations}
    ledgers_by_seq = {}

    # ledger_hash -> [{raw_validation}]
    validations = {}

    unl = []
    prev_len = 0
    try:
        with open(filename) as fh:
            for line in fh:
                # optimisation to avoid wasting expensive regexs
                if (
                    "LedgerConsensus:DBG Built ledger" not in line
                    and "LedgerMaster:NFO Advancing accepted ledger to" not in line
                    and "NetworkOPs:DBG VALIDATION: validation:" not in line
                ):
                    continue

                built = built_re.findall(line)
                if built:
                    timestamp = dateutil.parser.parse(built[0][0])
                    seq = int(built[0][1])
                    ledger_hash = built[0][2]
                    if seq in advancings:
                        ledgers_by_hash[ledger_hash] = {
                            "seq": seq,
                            "built_latency": timestamp_to_seconds(
                                advancings[seq].timestamp() - timestamp.timestamp()
                            ),
                            "hash": ledger_hash,
                            "latency": None,
                            "timestamp": advancings[seq],
                            "validations": {},
                        }
                        ledgers_by_seq[seq] = ledgers_by_hash[ledger_hash]
                        del advancings[seq]
                    else:
                        builts[seq] = {
                            "timestamp": timestamp,
                            "ledger_hash": ledger_hash,
                        }
                    continue

                advancing = advancing_re.findall(line)
                if advancing:
                    timestamp = dateutil.parser.parse(advancing[0][0])
                    seq = int(advancing[0][1])
                    if seq in builts:
                        ledgers_by_hash[builts[seq]["ledger_hash"]] = {
                            "seq": seq,
                            "built_latency": timestamp_to_seconds(
                                timestamp.timestamp()
                                - builts[seq]["timestamp"].timestamp()
                            ),
                            "hash": builts[seq]["ledger_hash"],
                            "latency": None,
                            "timestamp": timestamp,
                            "validations": {},
                        }
                        ledgers_by_seq[seq] = ledgers_by_hash[
                            builts[seq]["ledger_hash"]
                        ]
                        del builts[seq]
                    else:
                        advancings[seq] = timestamp
                    continue

                validation = validation_re.findall(line)

                # if validation is trusted
                if validation and int(validation[0][9]) == 1:
                    ledger_hash = validation[0][1]
                    # if we already have a ledger for this validation, fill it otherwise cache validations for later
                    if ledger_hash in ledgers_by_hash:
                        master_key = validation[0][12]
                        if master_key not in unl:
                            unl.append(master_key)
                        ledger = ledgers_by_hash[ledger_hash]
                        timestamp = dateutil.parser.parse(validation[0][0])
                        delta = timestamp_to_seconds(
                            ledger["timestamp"].timestamp() - timestamp.timestamp()
                        )
                        ledger["validations"][master_key] = delta
                    else:
                        if ledger_hash in validations:
                            validations[ledger_hash].append(validation)
                        else:
                            validations[ledger_hash] = [validation]
                    continue

                if prev_len < len(ledgers_by_hash) and len(ledgers_by_hash) % 100 == 0:
                    print(f"Parsed {len(ledgers_by_hash)} ledgers")
                prev_len = len(ledgers_by_hash)

    except FileNotFoundError:
        print(f"Error: Log file not found at: {filename}")
        return None
    except Exception as e:
        print(f"Error: Unexpected error occurred: {e}")
        return None

    for ledger_hash, lgr_validations in validations.items():
        if ledger_hash in ledgers_by_hash:
            for validation in lgr_validations:
                master_key = validation[0][12]
                ledger = ledgers_by_hash[ledger_hash]
                timestamp = dateutil.parser.parse(validation[0][0])
                delta = timestamp_to_seconds(
                    ledger["timestamp"].timestamp() - timestamp.timestamp()
                )
                ledger["validations"][master_key] = delta

    seqs = list(ledgers_by_seq.keys())
    seqs.sort()

    ledgers = []

    prev = None
    for seq in seqs:
        ledger = ledgers_by_seq[seq]
        if prev is not None:
            prev_ledger = ledgers_by_seq[prev]
            ledger["latency"] = timestamp_to_seconds(
                ledger["timestamp"].timestamp() - prev_ledger["timestamp"].timestamp()
            )
            late = 0
            for value in ledger["validations"].values():
                if value < 0:
                    late += 1
            ledger["validations_total"] = len(ledger["validations"])
            ledger["validations_late"] = late
        else:
            ledger["latency"] = 0
            for v in unl:
                if v not in ledger["validations"]:
                    ledger["validations"][v] = None
        ledgers.append(ledger)

    return ledgers


def stats(some_list):
    return (
        statistics.mean(some_list),
        statistics.median(some_list),
        statistics.stdev(some_list),
    )


def create_report(ledgers, threshold):
    # Analyzes the list of parsed ledgers to generate a comprehensive statistical
    # report on network and validator performance.
    #
    # The generated report contains the following metrics:
    #
    # 1. Overall Ledger Analysis:
    #    - The start and end timestamps of the analysis period.
    #    - The total number of ledgers closed by the node.
    #    - Statistical analysis (mean, median, stdev) of the time between
    #      consecutive ledger closes.
    #    - A total count and list of specific ledger sequence gaps (e.g., 8033-8035).
    #    - A list of ledgers whose close time exceeded a configurable threshold,
    #      including the sequence number and close duration.
    #
    # 2. UNL Validator Analysis:
    #    - A summary section for all validators combined, including:
    #      - The total number of unique validators.
    #      - The total number of validations received, missed, and late.
    #      - Statistical analysis of validation latency relative to the node's
    #        consensus time.
    #    - A detailed breakdown for each individual validator with the same
    #      set of metrics (received, missed, late, and latency stats).

    print(f"Generating statistics")
    prev_timestamp = None
    prev_seq = None
    ledger_durations = []
    validations = {}
    first = True
    report = {
        "start_date": ledgers[0]["timestamp"],
        "end_date": ledgers[len(ledgers) - 1]["timestamp"],
        "duration": ledgers[len(ledgers) - 1]["timestamp"] - ledgers[0]["timestamp"],
        "duration_seconds": ledgers[len(ledgers) - 1]["timestamp"].timestamp()
        - ledgers[0]["timestamp"].timestamp(),
        "ledgers": len(ledgers),
        "gaps": [],
        "over_threshold": [],
    }
    for ledger in ledgers:
        sample = ledger
        timestamp = sample["timestamp"]
        seq = sample["seq"]
        vals = sample["validations"]
        if first:
            for validator in vals:
                validations[validator] = [0, []]
            first = False
        else:
            ledger_duration = timestamp.timestamp() - prev_timestamp.timestamp()
            ledger_durations.append(ledger_duration)
            if seq - prev_seq > 1:
                report["gaps"].append(
                    {"start": prev_seq, "end": seq, "timestamp": timestamp}
                )
            if ledger_duration > threshold:
                report["over_threshold"].append(
                    {"seq": seq, "duration": ledger_duration, "timestamp": timestamp}
                )

        for validator, lag in vals.items():
            if lag is None:
                validations[validator][0] += 1
            else:
                validations[validator][1].append(lag)

        prev_timestamp = timestamp
        prev_seq = seq

    report["gaps_total"] = len(report["gaps"])
    report["over_threshold_total"] = len(report["over_threshold"])
    ledger_mean, ledger_median, ledger_stdev = stats(ledger_durations)
    report["ledger_time"] = {
        "mean": ledger_mean,
        "median": ledger_median,
        "stdev": ledger_stdev,
    }

    # summarize

    all_validations = []
    total_missed = 0
    total_after = 0
    for validator, data in validations.items():
        total_missed += data[0]
        vals = data[1]
        all_validations.extend(vals)
        for v in vals:
            if v <= 0:
                total_after += 1

    mean, median, stdev = stats(all_validations)

    report["valiadations"] = {
        "validators_total": len(validations),
        "validations_total": len(all_validations),
        "validations_missed": total_missed,
        "validations_late": total_after,
        "validations_mean": mean,
        "validations_median": median,
        "validations_stdev": stdev,
    }

    validators = []
    for key in sorted(validations.keys()):
        missed = validations[key][0]
        vals = validations[key][1]
        mean, median, stdev = stats(vals)
        after = 0
        for v in vals:
            if v <= 0:
                after += 1
        validators.append(
            {
                "master_key": key,
                "validations_total": len(vals),
                "validations_missed": missed,
                "validations_late": after,
                "validations_mean": mean,
                "validations_median": median,
                "validations_stdev": stdev,
            }
        )
    report["validators"] = validators

    return report


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        prog="RippledLogParser",
        description="This program parses rippled ledger validation and build logs to calculate local ledger build latency, ledger latency and UNL validator latencies."
        + " The program assumes that rippled LedgerConsensus and NetworkOPs components are logging at debug level, and LedgerMaster is logging at info level.",
    )
    arg_parser.add_argument("file", help="Path to rippled log file.")
    arg_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="stdout",
        help="The file name where the program output should be printed. Default is stdout.",
    )
    arg_parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=10.0,
        help="Threshold for logging ledger closes individually.",
    )
    arg_parser.add_argument(
        "-R",
        "--raw-output",
        type=str,
        default="",
        help="Output file to save processed log files",
    )
    arg_parser.add_argument(
        "-r",
        "--report",
        type=bool,
        default=True,
        help="Generate report summarizing validation logs",
    )
    args = arg_parser.parse_args()

    ledgers = parse_ledgers(args.file)
    if args.raw_output != "":
        with open(args.raw_output, "w") as f:
            f.write(json.dumps(ledgers, default=str, indent=2))

    if args.report:
        report = create_report(ledgers, args.threshold)
        with open(args.output, "w") as f:
            f.write(json.dumps(report, default=str, indent=2))


if __name__ == "__main__":
    main()
