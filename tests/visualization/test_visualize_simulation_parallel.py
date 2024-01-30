import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
from joblib import Parallel, delayed


def perform_update_and_visualize(TB, Update, sticky, output_file):
    """
    Perform update and visualize simulation for a given Update method and stickiness.
    """
    with open(output_file, "a") as file, contextlib.redirect_stdout(file):
        print(f"First, the {'sticky' if sticky else 'non-sticky'} case of {Update.__name__} piece:")
        TB.reset()
        i = 0
        while i < TB.steps:
            i = Update(i, rot=0, sticky=sticky)
            if i == -1:
                print("Game Over, reach the top")
                break
        TB.visualize_simulation(video_filename=f"{Update.__name__}_{'sticky' if sticky else 'Non-sticky'}.mp4",
                                plot_title=f"{Update.__name__} {'sticky' if sticky else 'Non-sticky'}")


def test_visualize_simulation():
    output_file = "test_visualize_simulation_output.txt"

    TB = Tetris_Ballistic(seed=42, width=10, height=20, steps=200)
    TB.save_config("test_visualize_simulation_config.yaml")

    ListUpdate = [TB.Update_1x1,
                  TB.Update_O,
                  TB.Update_I,
                  TB.Update_T,
                  TB.Update_L,
                  TB.Update_J,
                  TB.Update_S,
                  TB.Update_Z]

    # Parallel execution for sticky and non-sticky cases
    Parallel(n_jobs=len(ListUpdate))(delayed(perform_update_and_visualize)(TB, Update, True, output_file) for Update in ListUpdate)
    Parallel(n_jobs=len(ListUpdate))(delayed(perform_update_and_visualize)(TB, Update, False, output_file) for Update in ListUpdate)
