#!/usr/bin/env python3

import os
import numpy as np
import joblib
import glob
from scipy import stats
import matplotlib.pyplot as plt
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
import argparse


def PlotFluctuations(piece_id: int, type_: str, width: int, number: int = 0, output_filename: str = None):
    """
    Plots the logarithmic fluctuations over time for Tetris Ballistic
    simulations based on the specified piece ID, type, and width. It calculates
    the mean logarithmic fluctuations and the two-sided 95% confidence
    interval, plotting these along with individual simulation fluctuations
    against logarithmic time.

    Parameters:
    - piece_id (int): Identifier for the Tetris piece to be analyzed.
    - type_ (str): Type of the piece arrangement. Valid options are 'sticky',
      'non-sticky', and 'combined'.
    - width (int): Width of the simulation grid.
    - number (int, optional): Number of paths to show in the plot. If not
      provided, all paths are shown.
    - output_filename (str, optional): Name of the file to save the plot. If
      not provided, a default name is constructed using the format
      "Plot_{piece_id}_{type_}_w={width}.png".

    The function searches for simulation data files matching the pattern
       `./config_piece_{piece_id}_{type_}_w={width}*.joblib`

    loads each simulation, and calculates the logarithmic fluctuations. It then
    truncates these fluctuations to the length of the shortest simulation to
    standardize their lengths, computes the mean fluctuations and the
    confidence interval, and plots these against the logarithm of time steps.
    Additional reference lines for slopes of 1/3 and 1/2 are plotted for
    comparison.

    The plot includes individual fluctuations from each simulation, the mean
    fluctuation curve, and the upper and lower bounds of the 95% confidence
    interval, alongside the reference slope lines. The final plot is saved to
    the specified output filename and displayed.

    """

    pattern = f"./config_piece_{piece_id}_{type_}_w={width}*.joblib"

    # Use glob to find files matching the pattern
    files = glob.glob(pattern)

    TBs = []
    logfluctuations = []
    MaxStep = 0
    MinStep = float('inf')
    NumberSimulations = 0
    # Loop over the files and load them
    for file_path in files:
        NumberSimulations += 1
        TB = Tetris_Ballistic.load_simulation(file_path)
        MaxStep = max(MaxStep, TB.FinalSteps)
        MinStep = min(MinStep, TB.FinalSteps)
        TBs.append(TB)
        fl = np.log10(TB.Fluctuation[:TB.FinalSteps])
        logfluctuations.append(fl)
        if number > 0 and NumberSimulations == number:
            break

    # Truncate each array to MinStep length
    truncated_logfluctuations = np.array([fl[:MinStep] for fl in logfluctuations])

    # Compute the mean of these truncated arrays
    mean_logfluctuations = np.mean(truncated_logfluctuations, axis=0)

    # Calculate the standard deviation at each step
    std_deviation = np.std(truncated_logfluctuations, axis=0, ddof=1)

    # Calculate the Standard Error of the Mean (SEM)
    SEM = std_deviation / np.sqrt(NumberSimulations)

    # Degrees of freedom
    df = NumberSimulations - 1

    # t-critical value for 95% confidence interval
    t_critical = stats.t.ppf(1 - 0.025, df)

    # Calculate the confidence interval bounds
    ci_lower = mean_logfluctuations - t_critical * SEM
    ci_upper = mean_logfluctuations + t_critical * SEM
    print(f"mean of SEM: {np.mean(SEM)}, t_critical: {t_critical}")

    # Create a single figure and axis for plotting
    fig, ax = plt.subplots(figsize=(10, 6))

    logtime = np.log10(np.array(range(1, MaxStep + 1)))

    # Iterate over the list of arrays and plot each one on the same axis
    for i, arr in enumerate(logfluctuations):
        ax.plot(logtime[:len(arr)], arr, alpha=0.1)

    ax.plot(logtime, 1 / 3 * logtime, label="Slope 1/3", linestyle="--", color="red", linewidth=4)
    ax.plot(logtime, 1 / 2 * logtime, label="Slope 1/2", linestyle="--", color="blue", linewidth=4)

    ax.plot(logtime[:MinStep], mean_logfluctuations, label="Mean", linestyle="--", color="black", linewidth=4)
    ax.plot(logtime[:MinStep], ci_lower, label="Lower 95% CI", linestyle="-.", color="green", linewidth=4)
    ax.plot(logtime[:MinStep], ci_upper, label="Upper 95% CI", linestyle="-.", color="green", linewidth=4)

    # Set titles and labels
    ax.set_title(f'Logarithmic Fluctuations of {NumberSimulations} paths for Piece {piece_id} ({type_}) with Width {width}')
    ax.set_xlabel('Log Time')
    ax.set_ylabel('Log Fluctuations')
    ax.legend()

    # Saving the plot to the specified output filename
    plt.tight_layout()

    if output_filename is None:
        output_filename = f"Plot_piece_id={piece_id}_{type_}_w={width}_numberpaths={NumberSimulations}.png"

    plt.savefig(output_filename)
    plt.show()


if __name__ == "__main__":
    # Create the parser
    parser = argparse.ArgumentParser(description='Analyze Tetris Ballistic simulations.')

    # Add arguments with shorter versions
    parser.add_argument('-w',
                        '--width',
                        type=int,
                        required=True,
                        help='Specify the width')
    parser.add_argument('-p',
                        '--piece_id',
                        type=int,
                        required=True,
                        help='Specify the piece ID')
    parser.add_argument('-t',
                        '--type',
                        choices=['sticky', 'non-sticky', 'combined'],
                        required=True,
                        help='Specify the type: sticky, non-sticky, or combined')
    parser.add_argument('-n',
                        '--number',
                        type=int,
                        default=0,
                        help='Specify the number of paths to show. Default is 0, which is to show all paths.')
    parser.add_argument('-f',
                        '--output_filename',
                        type=str,
                        default=None,
                        help='Specify the output filename for the plot. Default is constructed if not provided.')

    # Parse the arguments
    args = parser.parse_args()

    PlotFluctuations(args.piece_id, args.type, args.width, args.number, args.output_filename)

# PlotFluctuations(piece_id=0, type_="sticky", width=50)
