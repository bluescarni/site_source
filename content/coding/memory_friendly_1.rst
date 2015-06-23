Memory-friendly data structures in Piranha - 1
##############################################

:tags: c++,coding,piranha
:summary: Smashing the memory wall, one cache hit at a time

Introduction
************

A significant trend in the evolution of computer hardware over the past few decades
is the so-called `memory wall`_. This term commonly designates the growing discrepancy between
the speed of the CPU and the speed of RAM: whereas CPU performance has kept a steady growth,
the speed of RAM has increased at a much slower pace. As a consequence, modern CPUs can end
up spending most of the time waiting for data to be delivered from the main memory (instead
of doing useful work).

.. _memory wall: https://en.wikipedia.org/wiki/Random-access_memory#Memory_wall

One of the approaches adopted by hardware manufacturers to ameliorate the memory wall problem
is that of equipping CPUs with `cache memory`_. Cache memory is very fast (but very
expensive and very small) memory residing directly on the CPU. Accessing data from the cache can be
orders of magnitudes faster than loading data from RAM, and modern CPUs typically feature
a complex multi-level hierarchy of caches. The efficient
exploitation of the memory hierarchy has become today a fundamental aspect of performance optimisation.

.. _cache memory: https://en.wikipedia.org/wiki/CPU_cache

Although the implementation details of cache memory hierarchies vary across CPUs, there are
two fundamental ideas that are broadly applicable:

* *temporal locality*: when data is loaded from RAM into the cache memory, it will be kept
  in the cache for some time (typically until it gets kicked out to make room for other data).
  It is thus important, once the data is in the cache, to try to run any computation that needs
  that data as soon as possible. It would be a waste to have the data removed from the cache,
  only to reload it later from RAM for further processing;
* *spatial locality*: loading data from RAM into the cache typically proceeds by chunks. If
  some data is loaded from RAM, it is likely that also other contiguous data will
  be loaded in the cache at the same time. Memory structures, such as C arrays and C++ vectors,
  that store data contiguously are, in this sense, cache-friendly: by paying the price
  of loading an element of the vector into the cache, you also get a bunch of nearby elements
  for free.

It is important to note that not all computational workloads benefit from cache-friendly
algorithms and data structures. An example in scientific computing is that of numerical
integration of ODEs, which essentially consists of an iterative loop in which the state of
the system is continuously updated. Normally, the ratio between the time spent moving and managing data
(i.e., the state vector) and actually doing computations with that data is very small, and all the
data needed for the computation fits in the cache memory.

On the other hand, algorithms that employ large data structures can be particularly vulnerable to
the memory wall. A classical example is linear algebra: when matrices and vectors are larger
than the available cache memory, it becomes crucial to employ optimisations such as
`loop tiling`_ in order to promote temporal locality and make sure that as much computation as possible
is performed on data currently residing in cache.

.. _loop tiling: https://en.wikipedia.org/wiki/Loop_nest_optimization

Sparse data structures are also problematic. In this context, with the admittedly-fuzzy "sparse" moniker
I mean structures which feature one or more of the following:

* frequent allocation of dynamic memory,
* non-contiguous data storage and/or traversal,
* pointer chasing.

Trees, lists, hash tables, and many other data structures can be considered sparse according to this
definition (at least in their most common implementations). The biggest problem with sparse structures is
that the memory access pattern is unpredictable, and spatial locality is not promoted.

One of the main focuses of `Piranha`_ is the manipulation of very large algebraic objects, such as multivariate
polynomials and Poisson series, commonly encountered in celestial mechanics.
This is a computational workload in which large amounts of data are generated
quickly from small input data. Take for instance the following symbolic multiplication:

.. math::

   \left(1+x+y+2z^2+3t^3+5u^5\right)^{12} \times \left(1+u+t+2z^2+3y^3+5x^5\right)^{12}.

.. _Piranha: https://github.com/bluescarni/piranha

Each multiplicand is a sparse multivariate polynomial with 6188 terms. The result, once fully expanded, will have 5821335 terms,
thus requiring circa 1000 times the storage space of each multiplicand. Additionally, storage schemes for multivariate polynomial
are typically sparse (dense storage is often appropriate for univariate polynomials, but it tends to be impractical
for multivariate polynomials). Efficient exploitation of the memory hierarchy is thus one of the primary focuses (and sources of
complications) in Piranha.

In this series of posts, I will detail some of the strategies adopted in Piranha in order to maximise spatial locality. Specifically,
I will be focusing on three foundational components:

* an arbitrary-precision integer class,
* a small vector class,
* a cache-friendly hash set.

The main theme in all three cases is that of minimising dynamic memory allocation.

The ``integer`` class
*********************

Piranha, like most computer algebra systems, provides an arbitrary-precision integral type, surprisingly called ``integer``.
As the name suggests, and contrary to the builtin C++ integral types, ``integer`` can represent any finite signed integral value, provided
enough memory is available.

The gold standard in arbitrary-precision arithmetic is the `GMP library`_, and most computer algebra libraries end up wrapping the
GMP ``mpz_t`` struct, in one form or another. Piranha is no exception, and ``integer`` is indeed (at least in part) a wrapped ``mpz_t``.

.. _GMP library: https://gmplib.org/

One of the problems of the ``mpz_t`` type is that *any* correctly initialised ``mpz_t`` ends up allocating dynamic memory, even if the
stored value is zero or if it fits in one of the standard integral C++ types. This is not much of a concern when one is using GMP to do computations
on gigantic integers, but it can be a problem when ``mpz_t`` is used to represent many not-so-large coefficients in a sparse multivariate
polynomial (a typical occurrence in celestial mechanics computations). As explained above, dynamic memory allocation can be very detrimental
to the performance of the memory subsystem.

The ``integer`` class in Piranha adopts then a small-value optimisation: if the value stored in the ``integer`` is not too large, it will be
stored directly in the static memory provided by the class itself, thus avoiding any dynamic allocation. When the stored value becomes large
enough, the storage will be switched to a normal ``mpz_t`` struct.

There are many ways in which the small-value optimisation can be implemented, with different tradeoffs between raw performance, memory utilisation
and standard compliance. The solution adopted in Piranha aims to be fully standard-conformant, and exploits the capabilities of the new `unrestricted unions`_
available in C++11.

.. _unrestricted unions: https://en.wikipedia.org/wiki/C%2B%2B11#Unrestricted_unions

Anatomy of an ``mpz_t``
=======================

A GMP ``mpz_t`` is, conceptually, rather simple. On my computer, the struct is defined as:

.. code-block:: c++

   typedef struct
   {
       int _mp_alloc;
       int _mp_size;
       mp_limb_t *_mp_d;
   } __mpz_struct;

   typedef __mpz_struct mpz_t[1];

(so ``mpz_t`` is actually an array of size 1 of ``__mpz_struct`` - this is a common technique used to pass by reference in C)

The exact types contained in the structure will vary across platforms, but the general idea is the following:

* ``_mp_alloc`` is a non-negative integral representing how many limbs are allocated. In an initialised ``mpz_t``, ``_mp_alloc`` is never zero;
* ``_mp_size`` is an integral corresponding to the number of limbs used to represent the value. If ``_mp_size`` is zero,
  then the stored value is zero, if ``_mp_size`` is positive then the stored value is positive, and if ``_mp_size`` is negative then the stored value
  is negative. The absolute value of ``_mp_size`` is never greater than ``_mp_alloc``;
* ``_mp_d`` is a pointer to a dynamically-allocated array of limbs.

In the GMP jargon, a limb is an unsigned integral value (typically of type ``unsigned long`` or ``unsigned long long``)
which represents a "chunk" of the number in binary form (exactly in the same way as a digit from 0 to 9 represents a chunk of a number in decimal form).
The least significant chunks of a number are stored first in an ``mpz_t``.

As an example, consider the number -173, which is represented in binary as

.. math::

   -10101101.

On a hypothetical 4-bit architecture, we can divide the absolute value of this number into the two 4-bit limbs:

.. math::

   \left[ 1101, 1010 \right].

Notice how the least-significant chunk, 1101, is stored first. Then a valid ``mpz_t`` representation of this number will have ``_mp_alloc`` set to at least 2, ``_mp_size``
will be set to -2 (as the number is negative), and ``_mp_d`` will be a pointer to a dynamically allocated array of limbs of size at least 2 containing the values 13
(which is 1101 in decimal form) and 10 (which is 1010 in decimal form). The absolute value of the number can be reconstructed from the limbs via additions and multiplications
by powers of two:

.. math::

   173 = 13 + 10 \cdot 2^4.

A static counterpart to ``mpz_t``
=================================

In order to implement the small-value optimisation, Piranha first introduces a class called ``static_integer`` which looks more or less like this:

.. code-block:: c++

   class static_integer
   {
       int _mp_alloc;
       int _mp_size;
       std::array<mp_limb_t,2> m_limbs;
   };

(this is a simplified version, the real logic in the selection of the types in the class is more complicated - but this is not relevant for this discussion)

``static_integer`` looks very similar to ``mpz_t``: the first two members are the same, but the third member has now become an ``std::array`` of 2 limbs.
The ``m_limbs`` member will be used to store values whose magnitude is not greater than two limbs (e.g., on a 64-bit architecture ``static_integer`` can store
absolute values from :math:`0` to :math:`2^{128} - 1`). The important point  is that ``std::array`` does not allocate dynamic memory, and thus operating on a ``static_integer``
is more cache-friendly than operating on an ``mpz_t``: there is no pointer chasing, and a single memory load will probably be enough to transfer the data from RAM
into the cache.

On its own, the ``static_integer`` class has a limited range and it is not very useful: we have merely extended the numerical range with respect to the
builtin C++ integral types. We will need to couple it to an ``mpz_t`` in order to create a true multiprecision integer.

Merging static and dynamic
==========================

Now comes the crucial part. We need to merge in a single entity the ``mpz_t`` struct and ``static_integer``: as long as the value we are representing is sufficiently
small, we will be exploiting the inline storage of ``static_integer``; when the value becomes too large, we will switch to the dynamic storage of a standard ``mpz_t``.

The natural tool to implement this merged entity is, in C++, a `union`_. Before C++11, unions used to be fairly limited. Specifically, it was not possible to store
in a union any non-`POD`_ (plain old data) type. In C++11, this restriction has been lifted.

.. _union: https://en.wikipedia.org/wiki/Union_type
.. _POD: http://en.cppreference.com/w/cpp/concept/PODType

The merged union in Piranha's ``integer`` type looks simply like this:

.. code-block:: c++

   union integer_union
   {
       static_integer m_st;
       mpz_struct_t m_dy;
   };

The management of a union in C/C++ rests completely on the shoulders of the developer. For instance, the developer must manually call the constructors and destructors
of the union members whenever it is needed to switch from one active member to the other (in C, it is sufficient to write into a member to make that member active).

Additionally, there is no way specified by the language to detect which element
of the union is the active one. It is thus common to include the union as a member of a wrapping class which adds an extra member representing which element
of the union is currently active. According to this model, the ``integer`` class would then look like this:

.. code-block:: c++

   class integer
   {
       integer_union m_union;
       bool m_tag;
   };

The ``m_tag`` member will be used to record which of the two members of the union is currently active. The developer has to take care of updating the tag each time
the active member of the union is switched.

It turns out that in this specific case we can avoid adding such a tagging member (which adds a noticeable size overhead due to padding).
The ``integer`` class exploits a special rule in the standard (section 9.2) which essentially
states the following: if the members of a union share a common initial sequence of members, then it is legal to access such initial sequence from any member of the union (note
that the actual rule is slightly more complicated, but it does not matter here). ``static_integer`` and the ``mpz_t`` struct do indeed share such a common initial sequence:

.. code-block:: c++

   int _mp_alloc;
   int _mp_size;

These two members are present at the beginning of both ``static_integer`` and ``mpz_t``. Under the special rule quoted above, the following is then legal:

.. code-block:: c++

   integer_union u; // This will intialise either the static or the dynamic member,
                    // depending on the default constructor of the union.
   std::cout << u.m_st._mp_alloc << '\n';
   std::cout << u.m_dy._mp_alloc << '\n';

That is, we can access the ``_mp_alloc`` member common to both elements of the union either from ``m_st`` or ``m_dy``, and we will fetch exactly the same
value.

If now we recall that ``_mp_alloc`` is guaranteed to be nonzero in a correctly initialised ``mpz_t``, it should be evident at this point that we can
use the ``_mp_alloc`` member as our tagging mechanism, instead of an ad-hoc ``m_tag`` member: if ``_mp_alloc`` is zero, then the active member of the union is
the ``static_integer``, otherwise the active member is the ``mpz_t``. This allows us to roll the tagging mechanism directly into the union, and
to save memory space.
