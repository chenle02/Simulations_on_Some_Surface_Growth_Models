import numpy as np
import argparse
import subprocess
import matplotlib.pyplot as plt


def Random_Deposition(width, height, steps):
    """
    This is a function to simulate Random Deposition on a substrate. This is
    simulation for the independent boxes (sand) piling. All columns are
    independent.

    Parameters
    ----------
    width : int
        Width of the substrate.
    height : int
        Height of the substrate.
    steps : int
        Steps or times to run.

    Returns
    -------
    string
        Filename of the output substrate.
    """
    substrate = np.zeros((height, width))
    topmost = height - 1

    for step in range(steps):
        position = np.random.randint(0, width)
        landing_row = np.max(np.where(substrate[:, position] == 0))
        substrate[landing_row, position] = step + 1

        if landing_row < topmost:
            topmost = landing_row

        if (step + 1) % 200 == 0:
            print(
                f"Step: {step + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.10 or topmost <= 2:
            print(
                f"Stopped at step {step + 1}, Level at {height - topmost}/{height}")
            break

    outputfile = f"Substrate_{width}x{height}_Particles={steps}.txt"
    np.savetxt(outputfile, substrate, fmt="%d", delimiter=",")
    print(f"{outputfile} saved!")
    return outputfile


def Random_Deposition_Surface_Relaxation(width, height, steps):
    """
    This is a function to simulate Random Deposition on a substrate with the
    surface relaxation. Particle will seek the lowest left/right neighbors to
    land.

    This is simulation for the independent boxes (sand) piling with surface
    relaxation.

    Parameters
    ----------
    width : int
        Width of the substrate.
    height : int
        Height of the substrate.
    steps : int
        Steps or times to run.

    Returns
    -------
    string
        Filename of the output substrate.
    """
    substrate = np.zeros((height, width))
    topmost = height - 1

    for step in range(steps):
        position = np.random.randint(0, width)

        # Determine the lnading rows for middle, left, and right columns
        landing_row_mid = np.max(np.where(substrate[:, position] == 0))
        landing_row_left = np.max(
            np.where(substrate[:, max(position - 1, 0)] == 0))
        landing_row_right = np.max(
            np.where(substrate[:, min(position + 1, width - 1)] == 0)
        )

        # Surface relaxation
        if (
            landing_row_right > max(landing_row_mid, landing_row_left)
            and position < width - 1
        ):
            # Landing on the right column
            substrate[landing_row_right, position + 1] = step + 1
            landing_row = landing_row_right
        elif landing_row_left > landing_row_mid and position > 1:
            # Landing on the left column
            substrate[landing_row_left, position - 1] = step + 1
            landing_row = landing_row_left
        else:
            # Default, Landing in the middle column
            substrate[landing_row_mid, position] = step + 1
            landing_row = landing_row_mid

        if landing_row < topmost:
            topmost = landing_row

        if (step + 1) % 200 == 0:
            print(
                f"Step: {step + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.10 or topmost <= 2:
            print(
                f"Stopped at step {step + 1}, Level at {height - topmost}/{height}")
            break

    outputfile = f"Substrate_{width}x{height}_Particles={steps}_Relaxed.txt"
    np.savetxt(outputfile, substrate, fmt="%d", delimiter=",")
    print(f"{outputfile} saved!")
    return outputfile


def Ballistic_Deposition(width, height, steps):
    """
    Simulate Ballistic Deposition on a substrate. In this simulation, particles stick
    upon contact with the substrate or a deposited particle.

    This is simulation for snowflakes piling.

    Parameters
    ----------
    width : int
        Width of the substrate.
    height : int
        Height of the substrate.
    steps : int
        Number of particles to drop.

    Returns
    -------
    string
        Filename of the output substrate for Ballistic Deposition;
        A csv file contains the substrate state.
    """
    substrate = np.zeros((height, width))
    topmost = height - 1

    for step in range(steps):
        position = np.random.randint(0, width)

        # Determine the landing rows for middle, left, and right columns
        column_data = substrate[:, position]
        landing_positions = np.where(column_data > 0)
        if landing_positions[0].size > 0:
            landing_row_mid = np.min(landing_positions) - 1
        else:
            landing_row_mid = height - 1

        column_data = substrate[:, max(position - 1, 0)]
        landing_positions = np.where(column_data > 0)
        if landing_positions[0].size > 0:
            landing_row_left = np.min(landing_positions)
        else:
            landing_row_left = height - 1

        column_data = substrate[:, min(position + 1, width - 1)]
        landing_positions = np.where(column_data > 0)
        if landing_positions[0].size > 0:
            landing_row_right = np.min(landing_positions)
        else:
            landing_row_right = height - 1

        # Stick to the top neighbor
        landing_row = min(landing_row_mid, landing_row_left, landing_row_right)
        substrate[landing_row, position] = step + 1

        if landing_row < topmost:
            topmost = landing_row

        if (step + 1) % 200 == 0:
            print(
                f"Step: {step + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.10 or topmost <= 2:
            print(
                f"Stopped at step {step + 1}, Level at {height - topmost}/{height}")
            break

    outputfile = f"Substrate_{width}x{height}_Particles={steps}_BD.txt"
    np.savetxt(outputfile, substrate, fmt="%d", delimiter=",")
    print(f"{outputfile} saved!")
    return outputfile


def interface_width(filename):
    """
    Compute and visualize the interface width of a substrate from a given
    simulation.

    This function reads the substrate state from a file, calculates the
    interface width over time, and generates a log-log plot of the interface
    width. It also computes the slope of the log-log plot as a function of
    time.

    Parameters
    ----------
    filename : str
        The name of the file containing the substrate data.

    Returns
    -------
    numpy.ndarray
        Array containing the interface width calculated at each step; An image
        file with the same name as the input file, but with a .png extension.
        The file contains the statistical figures.
    """

    # Load substrate from file
    substrate = np.loadtxt(filename, delimiter=",")

    # Parameters
    height, width = substrate.shape
    print(f"Height: {height}, Width: {width}")
    steps = int(np.max(substrate))
    interface = np.zeros(steps)

    # Compute the interface width
    for step in range(1, steps + 1):
        # Create a copy of the substrate for visualization
        vis_substrate = np.copy(substrate)

        # Replace values greater than the current step with 0
        vis_substrate[vis_substrate > step] = 0

        top_envelope = Envelop(vis_substrate)
        average = np.mean(top_envelope)

        interface[step - 1] = 0
        for pos in range(width):
            interface[step -
                      1] += np.power(top_envelope[pos] - average, 2) / width
        interface[step - 1] = np.sqrt(interface[step - 1])

    # Assuming 'time' is your x-axis data and 'interface' is your y-axis data
    time = np.array(range(1, steps + 1))
    quarter_length = len(time) // 4  # Compute the one-fourth point

    slopes = []

    # Loop from one-fourth of t to all t
    for end in range(quarter_length, len(time) + 1):
        current_time = time[:end]
        current_interface = interface[:end]

        log_time = np.log(current_time)
        log_interface = np.log(current_interface)

        # Fit a linear regression to the log-log data of the current window
        slope, _ = np.polyfit(log_time, log_interface, 1)
        slopes.append(slope)

    # Convert slopes to a numpy array for further processing if needed
    slopes = np.array(slopes)

    # Create side-by-side plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # First plot: log-log plot of the interface width
    ax1.loglog(time, interface, "-o", label="Interface Width")
    ax1.set_xlabel("Log of Time (log(t)")
    ax1.set_ylabel("Interface Width in log")
    ax1.set_title("Log-Log plot of Interface Width vs Time")
    ax1.grid(True)

    # Second plot: slopes
    ax2.plot(time[quarter_length - 1:], slopes, "-o", label="Computed Slopes")
    # ax2.axhline(y=reference_slope, color='r', linestyle='--', label=f'Reference Slope {reference_slope}')
    ax2.axhline(y=1 / 2, color="r", linestyle="--",
                label="Reference Slope 1/2")
    ax2.axhline(y=1 / 3, color="r", linestyle="--",
                label="Reference Slope 1/3")
    ax2.axhline(y=1 / 4, color="r", linestyle="--",
                label="Reference Slope 1/4")
    ax2.set_xlabel("Time (t)")
    ax2.set_ylabel("Slope")
    ax2.set_title("Slope of the log-log plot as a function of log(t)")
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig(filename.replace(".txt", ".png"), dpi=300)
    # plt.show()

    return interface


def Envelop(substrate):
    """
    Compute the top envelope of a substrate.

    This function calculates the highest particle position in each column of the substrate.
    It is used to visualize the top envelope of the substrate in the simulation.

    Parameters
    ----------
    substrate : numpy.ndarray
        The substrate matrix to compute the envelop for.

    Returns
    -------
    numpy.ndarray
        Array representing the top envelope of the substrate.
    """
    height, width = substrate.shape
    top_envelope = np.zeros(width)
    for pos in range(width):
        if np.any(substrate[:, pos] > 0):  # If there's any nonzero value in the column
            top_envelope[pos] = np.argmax(substrate[:, pos] > 0) - 3
        else:
            top_envelope[pos] = height - 2
    return top_envelope


def main():
    """
    The main function to simulate different types of surface growth models
    based on the provided command-line arguments.

    This function sets up a command-line interface for simulating Random
    Deposition, Random Deposition with Surface Relaxation, or Ballistic
    Decomposition on a substrate. It accepts various parameters like width,
    height, and number of steps for the simulation. It also provides options
    for generating a movie of the simulation and calculating interface width.

    The function decides the type of simulation based on the arguments passed,
    performs the simulation, and then proceeds to calculate the interface
    width. If the movie generation option is selected, it invokes another
    script to generate the movie.

    To use the script from terminal, the following options are expected:

    -w, --width    : Width of the substrate (default: 100)
    -e, --height   : Maximum height of the substrate (default: 60)
    -s, --steps    : Number of particles to drop (default: 5000)
    -r, --relax    : Enable surface relaxation (default: False)
    -b, --BD       : Enable ballistic decomposition (default: False)
    -m, --movie    : Generate an mp4 movie of the simulation (default: False)

    It returns:

    1. A text file representing the substrate state.
    2. Statistical figures, including a log-log plot for the interface width and the estimated slope.
    3. (Optional) An mp4 movie of the simulation process.

    Example:

    .. code-block:: bash

        > ptyhon3 RD_CLI.py -w 100 -e 60 -s 5000 --BD --movie

    In this example, the script will simulate Ballistic Decomposition on a substrate of size 100x60 for 5000 steps. And the simulation movie will be generated.

    """

    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=100,
        help="Width of the substrate (default: 100)",
    )
    parser.add_argument(
        "-e",
        "--height",
        type=int,
        default=60,
        help="Maximum height of the substrate (default: 60)",
    )
    parser.add_argument(
        "-s",
        "--steps",
        type=int,
        default=5000,
        help="Number of particles to drop (default: 5000)",
    )
    parser.add_argument(
        "-r",
        "--relax",
        action="store_true",
        help="Surface Relaxation: go to the nearest lowest neighbor (default: False)",
    )
    parser.add_argument(
        "-b",
        "--BD",
        action="store_true",
        help="Ballistic decomposition (default: False)",
    )
    parser.add_argument(
        "-m",
        "--movie",
        action="store_true",
        help="Generate the mp4 movie (default: False)",
    )
    args = parser.parse_args()

    Outputfile = ""
    if args.relax:
        Title = "Random Decomposition with Surface Relaxation"
        Outputfile = Random_Deposition_Surface_Relaxation(
            args.width, args.height, args.steps
        )
        print(Title)
    elif args.BD:
        Title = "Ballistic Decomposition"
        Outputfile = Ballistic_Deposition(args.width, args.height, args.steps)
        print(Title)
    else:
        Title = "Random Decomposition"
        Outputfile = Random_Deposition(args.width, args.height, args.steps)
        print(Title)

    print("Computing the interface width...")
    interface_width(Outputfile)

    if args.movie:
        print("Generating the movie...")
        cmd = [
            "python3",
            "Visualize_RD.py",
            "--file",
            Outputfile,
            "--title",
            Title,
            "--envelop",
            "--average",
        ]
        subprocess.run(cmd)
    else:
        print("Do not generate the movie.")


if __name__ == "__main__":
    main()
