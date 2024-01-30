Introduction
============

This Python package offers a suite of tools designed for simulating various
random surface growth models. The foundational concepts and methodologies are
significantly influenced by the work presented in the book by
:cite:t:`barabasi.stanley:95:fractal` (1995) on fractal concepts in surface
growth.

It is known that the fluctuations in the surface growth models fall into a few
universality classes. The most famous one is the Kardar-Parisi-Zhang (KPZ)
equation :cite:t:`kardar.parisi.ea:86:dynamic`

.. math::
  :label: kpz

    \frac{\partial h(t,x)}{\partial t} = \nu \nabla^2 h(t,x) + \frac{\lambda}{2} (\nabla h(t,x))^2 + \eta(t,x), \quad t>0, x \in \mathbb{R},

where :math:`\eta` is a centered Gaussian noise, which is white in both space
and time. The KPZ equation :eq:`kpz` is a *stochastic partial differential
equation (SPDE)* :cite:`walsh:86:introduction`.


KPZ equation :eq:`kpz` was solved by :cite:t:`hairer:13:solving` in 2013. The
fluctuations of the KPZ equation :eq:`kpz` are in the KPZ universality class;
see :cite:t:`amir.corwin.ea:11:probability`. Numerous discrete models report the
same universality class as the KPZ universality class, including


+ the ballistic documentation model: :cite:`family.vicsek:85:scaling`, :cite:`meakin.ramanlal.ea:86:ballistic`, :cite:`family.vicsek:85:scaling`.
+ the Eden model: :cite:`baiod.kessler.ea:88:dynamical`, :cite:`plischke.racz:85:dynamic`, :cite:`jullien.botet:85:scaling` :cite:`meakin.jullien.ea:86:large-scale`, :cite:`zabolitzky.stauffer:86:simulation`.
+ solid-on-Solid model: ...

Theoretical results include the fluctuations of:

+ the longest increasing subsequence of a random permutation: :cite:`baik.deift.ea:99:on`.
+ the largest eigenvalue of a random matrix: :cite:`tracy.widom:93:level-spacing` and :cite:`tracy.widom:94:level`.
+ the asymmetric simple exclusion process (*ASEP*): :cite:`johansson:00:shape`
  and :cite:`tracy.widom:09:asymptotics`.

History of the Package
=======================

The foundational elements of this package, which include the random deposition,
random deposition with surface relaxation, the ballistic deposition models, and
a visualization component, were initially crafted by the first author. These
components, forming the basis of the package, were part of a graduate student
seminar in October 2023, as documented in :cite:t:`chen:23:graduate`. The
seminar's slides provide an excellent introduction to these foundational aspects
of the package.

Building upon this foundation, the package has been enriched with simulations
for growth models with Tetris pieces. This feature is to test the belief of the
universality of the growth models. This feature was developed as a final course
project for the course *"Math 7820: Applied Stochastic Processes I,"* undertaken
by the second and third authors in Fall 2023. This is still an ongoing project.
More feature and functionalities will be added in the future. Some simulation
experiments will be carried out to test the universality of the growth models.

Acknowledgments
================

The references throughout this document have been meticulously compiled and are
available in a comprehensive bibliography bank :cite:`chen:23:spdes-bib`.

This work is partially supported by the **National Science Foundation (NSF)**
under Grant No. `No. 2246850
<https://www.nsf.gov/awardsearch/showAward?AWD_ID=2246850>`_ (2023--2026) and
the collaboration/travel award from the **Simons foundation** under Award No.
959981 (2022--2027).


Bibliography
=============

.. bibliography::
