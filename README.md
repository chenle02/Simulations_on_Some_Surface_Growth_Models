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
# References
1. Le Chen's Graduate Student Seminar talk on surface growth models: [here](https://github.com/chenle02/Graduate_Student_Seminars_by_Le_Chen/blob/main/2023-11-01/readme.md).
2. Barabási and Stanley, ''Fractal Concepts in Surface Growth'', Cambridge University Press, 1995.

# License
MIT License
