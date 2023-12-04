# Simulations on Some Surface Growth Models
This repo contains some simulations for some surface growth models. It comes out of a final exam project for Math-7820 (Applied Stochastic Processes) Fall 2023 at Auburn.

## Scripts
1. `RD_CLI.py`
```shell
❯ ./RD_CLI.py --help
usage: RD_CLI.py [-h] [-w WIDTH] [-e HEIGHT] [-s STEPS] [--relax] [--BD] [-m]

    Simulate Random Deposition on a substrate.
    Outputs: 1. Substrate_WIDTHxHEIGHT_Particles=STEPS_[Relaxed/BD].txt
                A text file for the substrate.
             2. Statistical figures, loglog plot for the interface width and the estimated slope.

    Author: Le Chen (le.chen@auburn.edu, chenle02@gmail.com)
    Date: 2023-10-22



options:
  -h, --help            show this help message and exit
  -w WIDTH, --width WIDTH
                        Width of the substrate (default: 100)
  -e HEIGHT, --height HEIGHT
                        Maximum height of the substrate (default: 60)
  -s STEPS, --steps STEPS
                        Number of particles to drop (default: 5000)
  --relax               Surface Relaxation: go to the nearest lowest neighbor (default: False)
  --BD                  Ballistic decomposition (default: False)
  -m, --movie           Generate the mp4 movie (default: False)
```
2. `Visualize_RD.py`
```
❯ ./Visualize_RD.py --help
usage: Visualize_RD.py [-h] -f FILE [-t TITLE] [-r RATE] [-e] [-a] [-p]

    Visualization the decomposition of particles on a substrate
    Input: Substrate text file, produced by RD_CLI.py
    Output: mp4 video

    Author: Le Chen (le.chen@auburn.edu, chenle02@gmail.com)
    Date: 2023-10-22



options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  Path to the substrate
  -t TITLE, --title TITLE
                        Title of the plot (default: None)
  -r RATE, --rate RATE  Rate per frame (default: 4)
  -e, --envelop         Show the top envelop (default: False)
  -a, --average         Show the average height (default: False)
  -p, --play            Play the video after generation (default: False)


```
3. `tetris_complete.py`
```

❯ python3 tetris_complete.py --help
usage: tetris_complete.py [-h] [-w WIDTH] [-e HEIGHT] [-s STEPS]

    Simulate Random Deposition on a substrate.
    Outputs: 1. Substrate_WIDTHxHEIGHT_Particles=STEPS_[Relaxed/BD].txt
                A text file for the substrate.
             2. Statistical figures, loglog plot for the interface width and the estimated slope.

    Author: Ian Ruau and Mauricio Mountes
    Date: 2023-12-01



options:
  -h, --help            show this help message and exit
  -w WIDTH, --width WIDTH
                        Width of the substrate (default: 100)
  -e HEIGHT, --height HEIGHT
                        Maximum height of the substrate (default: 60)
  -s STEPS, --steps STEPS
                        Number of particles to drop (default: 5000)

```

# Documentation

* Documentation for the simulation on the random surface growth with Tetris pieces:
    1. Stable version (the main branch) in HTML is hosted on [Le's homepage](http://webhome.auburn.edu/~lzc0090/Simulation_Tetris/html/) or on [Read the Docs](https://simulations-on-some-surface-growth-models.readthedocs.io/main/).
    2. [Latest version](https://simulations-on-some-surface-growth-models.readthedocs.io/latest/) is pointing to the [Tetris_Domino branch](https://simulations-on-some-surface-growth-models.readthedocs.io/tetris_domino/), both are hosted on `Read the Docs`. 
    3. You can also download the [pdf](./docs/pdf/surfacegrowthwithrandomtetrispieces.pdf).

* Documentation for the simulation on the solid on solid model will come soon.

# References
1. Le Chen's Graduate Student Seminar talk on surface growth models: [here](https://github.com/chenle02/Graduate_Student_Seminars_by_Le_Chen/blob/main/2023-11-01/readme.md).
2. Barabási and Stanley, ''Fractal Concepts in Surface Growth'', Cambridge University Press, 1995.

# License
MIT License
