Overloading overloaded
######################

:tags: c++,coding
:summary: Overloading overloaded

Introduction
************

The fundamental idea of generic programming is that
of writing classes, algorithms and functions able to
operate on arbitrary types. In the jargon of modern C++, one says that
a software component defines a *concept* (i.e., a set of requirements)
of which a type ``T`` must be a *model* in order for ``T`` to be usable
with that component.

Take for instance the ``std::sort()`` function from the standard C++ library.
One of its prototypes `reads`_:

.. code-block:: c++

   template <class RandomIt>
   void sort(RandomIt first, RandomIt last);

.. _reads: http://en.cppreference.com/w/cpp/algorithm/sort

Among others, one of the requirements stipulated by ``std::sort()`` is that
the value type of ``RandomIt`` (that is, the type we are sorting) must be equipped
with a less-than operator (``std::sort()`` is a `comparison sort`_).
It is thus possible to sort out-of-the-box, for instance, vectors of integers
or floating point values (`disregarding NaNs`_ for a second). It will not however
be possible to sort instances of ``std::complex``, as ``operator<()`` is not implemented
for these types (C++ wisely does not get into the business of defining an ordering relation
for complex numbers).

.. _comparison sort: http://en.wikipedia.org/wiki/Comparison_sort
.. _disregarding NaNs: http://stackoverflow.com/questions/14784263/stdout-of-range-during-stdsort-with-custom-comparator

If the type we are sorting does not provide an ``operator<()``, we have a couple of possible options.

The first option is to use the other version of ``std::sort()`` provided by the standard library,
which reads:

.. code-block:: c++

   template <class RandomIt, class Compare>
   void sort(RandomIt first, RandomIt last, Compare comp);

Here the additional parameter ``comp`` must be a function-like object able to compare
instances of the value type according to some strict weak ordering relation
(here are the `gory details`_ in their standardese glory). This basically means
that we can tell ``std::sort()`` *how* instances of the value type should be compared
for sorting purposes. In the example of complex numbers, we might want to sort a vector
of complex values according to their norm, or maybe to their real or imaginary component,
depending on the context.

The second option is to equip


.. _gory details: http://en.cppreference.com/w/cpp/concept/Compare
