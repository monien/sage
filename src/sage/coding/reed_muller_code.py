r"""
Reed-Muller code

Given integers `m, r` and a finite field `F`
corresponding Reed Muller Code is the set:

.. math::

    \{ (f(\alpha_1), f(\alpha_2), \ldots, f(\alpha_n)  \mid  f \in F[x_1,x_2,\ldots,x_m], \deg f < r \}

This file contains the following elements:

    - :class:`QAryReedMullerCode`, the class for Reed Muller codes over non-binary field of size q and `r<q`
    - :class:`BinaryReedMullerCode`, the class for Reed Muller codes over binary field and `r<=m`
    - :class:`ReedMullerVectorEncoder`, an encoder with a vectorial message space (for both the two code classes)
    - :class:`ReedMullerPolynomialEncoder`, an encoder with a polynomial message space (for both the code classes)
"""
#*****************************************************************************
#       Copyright (C) 2016 Parthasarathi Panda <parthasarathipanda314@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#                  http://www.gnu.org/licenses/
#*****************************************************************************

from operator import mul
from sage.matrix.constructor import matrix
from sage.functions.other import binomial
from sage.calculus.var import var
from sage.misc.functional import symbolic_sum
from sage.coding.linear_code import AbstractLinearCode, LinearCodeSyndromeDecoder
from sage.coding.encoder import Encoder
from sage.combinat.subset import Subsets
from sage.combinat.tuple import Tuples
from sage.rings.finite_rings.finite_field_constructor import GF
from sage.rings.finite_rings.finite_field_base import FiniteField
from sage.rings.integer import Integer
from sage.modules.free_module_element import vector
from sage.rings.polynomial.polynomial_ring_constructor import PolynomialRing
from sage.interfaces.gap import gfq_gap_to_sage
from sage.interfaces.all import gap
from sage.misc.cachefunc import cached_method
from functools import reduce


def _binomial_sum(n, k):
    r"""
    Given ``n`` and ``k``, computes the number of subsets of a set with `n` distinct elements with cardinality`<=k`. Used to compute dimension of binomial reed muller code.
    INPUT:

        - ``n`` -- The cardinality of the super set.
        - ``k`` -- The upper limit on the size of the subset.

    EXAMPLES::

        sage: from sage.coding.reed_muller_code import _binomial_sum
        sage: _binomial_sum(4, 2)
        11
    """
    s = 1
    nCi = 1
    for i in range(k):
        nCi = ((n - i) * nCi) / (i + 1)
        s = nCi + s
    return s


def _multivariate_polynomial_interpolation(
        evaluation,
        num_of_var,
        order,
        polynomial_ring):
    r"""
    Given the evaluation of a multivariate polynomial of certain number of variables and certain degree over `F` on every point, this function returns the polynomial.
    INPUT:

        - ``evaluation`` -- A vector or a list of evaluation of the polynomial at all the points.

        - ``num_of_var`` -- The number of variables used in polynomial (i.e. `m`).

        - ``order`` -- The degree of the polynomial in question.

        - ``polynomial_ring`` -- The Polynomial Ring the polynomial in question is from

    EXAMPLES::

        sage: from sage.coding.reed_muller_code import _multivariate_polynomial_interpolation
        sage: F = GF(3)
        sage: R.<x,y> = F[]
        sage: v = vector(F, [1, 2, 0, 0, 2, 1, 1, 1, 1])
        sage: _multivariate_polynomial_interpolation(v, 2, 2, R)
        x*y + y^2 + x + y + 1
    """
    if num_of_var == 0 or order == 0:
        return evaluation[0]
    base_field = polynomial_ring.base_ring()
    q = base_field.cardinality()
    n_by_q = q**(num_of_var - 1)
    d = min(order + 1, q)
    multipoint_evaluation_list = []
    uni_poly_ring = PolynomialRing(base_field, 'x')
    base_field_zero = base_field.zero()
    for k in range(n_by_q):
        xcordinate = base_field.first()
        points = []
        for i in range(d):
            points.append((xcordinate, evaluation[k + i * n_by_q]))
            if (xcordinate != base_field.last()):
                xcordinate = base_field.next(xcordinate)
        polyVector = uni_poly_ring.lagrange_polynomial(
            points).coefficients(sparse=False)
        if len(polyVector) < d:
            # adding zeros to represet a (d-1) degree polynomial
            polyVector = polyVector + \
                [base_field_zero for i in range(d - len(polyVector))]
        multipoint_evaluation_list.append(polyVector)
    poly = polynomial_ring.zero()
    z = 1
    x = polynomial_ring.gen(num_of_var - 1)
    for k in range(d):  # computing the polynomial
        poly = poly + z * _multivariate_polynomial_interpolation([multipoint_evaluation_list[i][k] for i in range(n_by_q)],
                                                                 num_of_var - 1, order - k, polynomial_ring)
        z = z * x
    return poly


def ReedMullerCode(base_field, order, num_of_var):
    r"""
    Returns a Reed Muller code. If the given field is binary it returns a binary Reed Muller code, otherwise it returns a q-ary Reed Muller Code.

    INPUT:

    - ``base_field`` -- The finite field `F` over which code is built.

    - ``order`` -- The order of the Reed Muller Code, i.e., the maximum degree of the polynomial to be used in the code.

    - ``num_of_var`` -- The number of variables used in polynomial (i.e. `m`).

    EXAMPLES::

    A Reed-Muller code can be constructed by using a predefined field or using the value of q::

        sage: F = GF(3)
        sage: C = codes.ReedMullerCode(F, 2, 2)
        sage: C
        3-ary Reed Muller Code of order 2 and number of variables 2

    Simmilarly, using the finite field `F` of size 2 we can generate a binary reed muller code::

        sage: F = GF(2)
        sage: C = codes.ReedMullerCode(F, 2, 2)
        sage: C
        Binary Reed Muller Code of order 2 and number of variables 2

    .. WARNING::

        For q-ary reed muller codes, the order of reed muller code must be LESS THAN q. For now, this implementation only supports Reed-Muller codes whose order is less than q.
        Binary reed muller codes must have it's order less than or equal to the number of variables.

    .. WARNING::

        This version of the method is made available to the user only temporarily to maintain support for an older version of binary reed muller codes.
        It will be preferable for you if you use the function ReedMullerCode() to generate your code.

    """
    if not(isinstance(base_field, FiniteField)):
        raise ValueError("The parameter `base_field` must be a finite")
    q = base_field.cardinality()
    if q == 2:
        return BinaryReedMullerCode(order, num_of_var)
    else:
        return QAryReedMullerCode(base_field, order, num_of_var)


class QAryReedMullerCode(AbstractLinearCode):
    r"""
    Representation of a q-ary Reed Muller code with `r<q`.

    INPUT:

    - ``base_field`` -- The finite field `F` or the size of finite field `F` over which code is built.

    - ``order`` -- The order of the Reed Muller Code, i.e., the maximum degree of the polynomial to be used in the code.

    - ``num_of_var`` -- The number of variables used in polynomial (i.e. `m`).

    EXAMPLES::

    A Reed-Muller code can be constructed by using a predefined field or using the value of q::

        sage: from sage.coding.reed_muller_code import QAryReedMullerCode
        sage: F = GF(3)
        sage: C = QAryReedMullerCode(F, 2, 2)
        sage: C
        3-ary Reed Muller Code of order 2 and number of variables 2

    .. WARNING::

        For q-ary reed muller codes, the order of reed muller code must be LESS THAN q. For now, this implementation only supports Reed-Muller codes whose order is less than q.
    """

    _registered_encoders = {}
    _registered_decoders = {}

    def __init__(self, base_field, order, num_of_var):
        r"""
        TESTS:

        Note that the order given cannot be greater than (q-1). An error is raised if that happens::

            sage: from sage.coding.reed_muller_code import QAryReedMullerCode
            sage: C = QAryReedMullerCode(GF(3), 4, 4)
            Traceback (most recent call last):
            ...
            ValueError: The order must be less than 3

        The order and the number of variable must be integers::

            sage: C = QAryReedMullerCode(GF(3),1.1,4)
            Traceback (most recent call last):
            ...
            ValueError: The order of the code must be an integer

        The base_field parameter must be a finite field::

            sage: C = QAryReedMullerCode(QQ,1,4)
            Traceback (most recent call last):
            ...
            ValueError: the input `base_field` must be a FiniteField
        """
        # input sanitization
        if not(isinstance(base_field, FiniteField)):
            raise ValueError("the input `base_field` must be a FiniteField")
        if not(isinstance(order, Integer)):
            raise ValueError("The order of the code must be an integer")
        if not(isinstance(num_of_var, Integer)):
            raise ValueError("The number of variables must be an integer")
        q = base_field.cardinality()
        if (order >= q):
            raise ValueError("The order must be less than %s" % q)

        super(
            QAryReedMullerCode,
            self).__init__(
            base_field,
            q**num_of_var,
            "EvaluationVector",
            "Syndrome")
        self._order = order
        self._num_of_var = num_of_var
        self._dimension = binomial(num_of_var + order, order)

    def order(self):
        r"""
        Returns the order of ``self``.

        EXAMPLES::

            sage: from sage.coding.reed_muller_code import QAryReedMullerCode
            sage: F = GF(59)
            sage: C = QAryReedMullerCode(F, 2, 4)
            sage: C.order()
            2
        """
        return self._order

    def number_of_variables(self):
        r"""
        Returns the number of variables used in ``self``.

        EXAMPLES::

            sage: from sage.coding.reed_muller_code import QAryReedMullerCode
            sage: F = GF(59)
            sage: C = QAryReedMullerCode(F, 2, 4)
            sage: C.number_of_variables()
            4
        """
        return self._num_of_var

    def minimum_distance(self):
        r"""
        Returns the minimum distance of ``self``.

        EXAMPLES::

            sage: from sage.coding.reed_muller_code import QAryReedMullerCode
            sage: F = GF(5)
            sage: C = QAryReedMullerCode(F, 2, 4)
            sage: C.minimum_distance()
            375
        """
        d = self.order()
        q = self.base_field().cardinality()
        n = self.length()
        return ((q - d) * n) / q

    def _repr_(self):
        r"""
        Returns a string representation of ``self``.

        EXAMPLES::

            sage: from sage.coding.reed_muller_code import QAryReedMullerCode
            sage: F = GF(59)
            sage: C = QAryReedMullerCode(F, 2, 4)
            sage: C
            59-ary Reed Muller Code of order 2 and number of variables 4
        """
        return "%s-ary Reed Muller Code of order %s and number of variables %s" % (
            self.base_field().cardinality(), self.order(), self.number_of_variables())

    def _latex_(self):
        r"""
        Returns a latex representation of ``self``.

        EXAMPLES::

            sage: from sage.coding.reed_muller_code import QAryReedMullerCode
            sage: F = GF(59)
            sage: C = QAryReedMullerCode(F, 2, 4)
            sage: latex(C)
            59\textnormal{-ary Reed Muller Code of order} 2 \textnormal{and number of variables} 4
        """
        return "%s\\textnormal{-ary Reed Muller Code of order} %s \\textnormal{and number of variables} %s"\
            % (self.base_field().cardinality(), self.order(), self.number_of_variables())

    def __eq__(self, other):
        r"""
        Tests equality between Reed-Muller Code objects.

        EXAMPLES::

            sage: from sage.coding.reed_muller_code import QAryReedMullerCode
            sage: F = GF(59)
            sage: C1 = QAryReedMullerCode(F, 2, 4)
            sage: C2 = QAryReedMullerCode(GF(59), 2, 4)
            sage: C1.__eq__(C2)
            True
        """
        # I am not comparing the base field directly because of possible change
        # in variables
        return isinstance(other, QAryReedMullerCode) \
            and self.base_field().cardinality() == other.base_field().cardinality() \
            and self.order() == other.order() \
            and self.number_of_variables() == other.number_of_variables()


class BinaryReedMullerCode(AbstractLinearCode):
    r"""
    Representation of a binary Reed Muller code with `r<=m`.

    INPUT:

    - ``order`` -- The order of the Reed Muller Code, i.e., the maximum degree of the polynomial to be used in the code.

    - ``num_of_var`` -- The number of variables used in polynomial (i.e. `m`).

    EXAMPLES:

    A binary Reed-Muller code can be constructed by simply giving the order of the code and the number of variables::

        sage: C = codes.BinaryReedMullerCode(2, 4)
        sage: C
        Binary Reed Muller Code of order 2 and number of variables 4

    .. WARNING::
        The order of reed muller code here must be LESS THAN OR EQUAL TO the number of variables.
    """

    _registered_encoders = {}
    _registered_decoders = {}

    def __init__(self, order, num_of_var):
        r"""
        TESTS:

        If the order given is greater than the number of variables an error is raised::

            sage: C = codes.BinaryReedMullerCode(5, 4)
            Traceback (most recent call last):
            ...
            ValueError: The order must be less than or equal to 4

        The order and the number of variable must be integers::

            sage: C = codes.BinaryReedMullerCode(1.1,4)
            Traceback (most recent call last):
            ...
            ValueError: The order of the code must be an integer
        """
        # input sanitization
        if not(isinstance(order, Integer)):
            raise ValueError("The order of the code must be an integer")
        if not(isinstance(num_of_var, Integer)):
            raise ValueError("The number of variables must be an integer")
        if (num_of_var < order):
            raise ValueError(
                "The order must be less than or equal to %s" %
                num_of_var)

        super(
            BinaryReedMullerCode,
            self).__init__(
            GF(2),
            2**num_of_var,
            "EvaluationVector",
            "Syndrome")
        self._order = order
        self._num_of_var = num_of_var
        self._dimension = _binomial_sum(num_of_var, order)

    def order(self):
        r"""
        Returns the order of ``self``.

        EXAMPLES::

            sage: C = codes.BinaryReedMullerCode(2, 4)
            sage: C.order()
            2
        """
        return self._order

    def number_of_variables(self):
        r"""
        Returns the number of variables used in ``self``.

        EXAMPLES::

            sage: C = codes.BinaryReedMullerCode(2, 4)
            sage: C.number_of_variables()
            4
        """
        return self._num_of_var

    def minimum_distance(self):
        r"""
        Returns the minimum distance of ``self``.

        EXAMPLES::

            sage: C = codes.BinaryReedMullerCode(2, 4)
            sage: C.minimum_distance()
            4
        """
        return 2**(self.number_of_variables() - self.order())

    def _repr_(self):
        r"""
        Returns a string representation of ``self``.

        EXAMPLES::

            sage: C = codes.BinaryReedMullerCode(2, 4)
            sage: C
            Binary Reed Muller Code of order 2 and number of variables 4
        """
        return "Binary Reed Muller Code of order %s and number of variables %s" % (
            self.order(), self.number_of_variables())

    def _latex_(self):
        r"""
        Returns a latex representation of ``self``.

        EXAMPLES::

            sage: C = codes.BinaryReedMullerCode(2, 4)
            sage: latex(C)
            \textnormal{Binary Reed Muller Code of order} 2 \textnormal{and number of variables} 4
        """
        return "\\textnormal{Binary Reed Muller Code of order} %s \\textnormal{and number of variables} %s" % (
            self.order(), self.number_of_variables())

    def __eq__(self, other):
        r"""
        Tests equality between Reed-Muller Code objects.

        EXAMPLES::

            sage: C1 = codes.BinaryReedMullerCode(2, 4)
            sage: C2 = codes.BinaryReedMullerCode(2, 4)
            sage: C1.__eq__(C2)
            True
        """
        return isinstance(other, BinaryReedMullerCode) \
            and self.order() == other.order() \
            and self.number_of_variables() == other.number_of_variables()


class ReedMullerVectorEncoder(Encoder):
    r"""
    Encoder for Reed-Muller codes which encodes vectors into codewords.

    INPUT:

    - ``code`` -- The associated code of this encoder.

    EXAMPLES::

        sage: C1=codes.ReedMullerCode(GF(2), 2, 4)
        sage: E1=codes.encoders.ReedMullerVectorEncoder(C1)
        sage: E1
        Evaluation vector-style encoder for Binary Reed Muller Code of order 2 and number of variables 4
        sage: C2=codes.ReedMullerCode(GF(3), 2, 2)
        sage: E2=codes.encoders.ReedMullerVectorEncoder(C2)
        sage: E2
        Evaluation vector-style encoder for 3-ary Reed Muller Code of order 2 and number of variables 2

    Actually, we can construct the encoder from ``C`` directly::

        sage: C=codes.ReedMullerCode(GF(2), 2, 4)
        sage: E = C.encoder("EvaluationVector")
        sage: E
        Evaluation vector-style encoder for Binary Reed Muller Code of order 2 and number of variables 4
    """

    def __init__(self, code):
        r"""
        TESTS:

        If ``code`` is not a GRS code, an error is raised::

            sage: C  = codes.RandomLinearCode(10, 4, GF(11))
            sage: codes.encoders.ReedMullerVectorEncoder(C)
            Traceback (most recent call last):
            ...
            ValueError: the code has to be a Reed Muller code
        """
        if not (
            isinstance(
                code,
                QAryReedMullerCode) or isinstance(
                code,
                BinaryReedMullerCode)):
            raise ValueError("the code has to be a Reed Muller code")
        super(ReedMullerVectorEncoder, self).__init__(code)

    def _repr_(self):
        r"""
        Returns a string representation of ``self``.

        EXAMPLES::

            sage: F = GF(11)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: E=codes.encoders.ReedMullerVectorEncoder(C)
            sage: E
            Evaluation vector-style encoder for 11-ary Reed Muller Code of order 2 and number of variables 4
        """
        return "Evaluation vector-style encoder for %s" % self.code()

    def _latex_(self):
        r"""
        Returns a string representation of ``self``.

        EXAMPLES::

            sage: F = GF(11)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: E=codes.encoders.ReedMullerVectorEncoder(C)
            sage: latex(E)
            \textnormal{Evaluation vector-style encoder for }11\textnormal{-ary Reed Muller Code of order} 2 \textnormal{and number of variables} 4
        """
        return "\\textnormal{Evaluation vector-style encoder for }%s" % self.code()._latex_()

    def __eq__(self, other):
        r"""
        Tests equality between ReedMullerVectorEncoder objects.

        EXAMPLES::

            sage: F = GF(11)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: D1 = codes.encoders.ReedMullerVectorEncoder(C)
            sage: D2 = codes.encoders.ReedMullerVectorEncoder(C)
            sage: D1.__eq__(D2)
            True
            sage: D1 is D2
            False
        """
        return (isinstance(other, ReedMullerVectorEncoder)
                ) and self.code() == other.code()

    @cached_method
    def generator_matrix(self):
        r"""
        Returns a generator matrix of ``self``

        EXAMPLES::

            sage: F = GF(3)
            sage: C = codes.ReedMullerCode(F, 2, 2)
            sage: E = codes.encoders.ReedMullerVectorEncoder(C)
            sage: E.generator_matrix()
            [1 1 1 1 1 1 1 1 1]
            [0 1 2 0 1 2 0 1 2]
            [0 0 0 1 1 1 2 2 2]
            [0 1 1 0 1 1 0 1 1]
            [0 0 0 0 1 2 0 2 1]
            [0 0 0 1 1 1 1 1 1]
        """
        C = self.code()
        base_field = C.base_field()
        order = C.order()
        num_of_var = C.number_of_variables()
        q = base_field.cardinality()
        dimension = C.dimension()
        base_field_tuple = Tuples(base_field.list(), num_of_var)
        exponents = Subsets(range(num_of_var) *
                            min(order, (q - 1)), submultiset=True)
        matrix_list = []
        exponent = exponents.first()
        for i in range(dimension):
            matrix_list.append(
                [reduce(mul, [x[i] for i in exponent], 1) for x in base_field_tuple])
            exponent = exponents.next(exponent)
        return matrix(base_field, matrix_list)


class ReedMullerPolynomialEncoder(Encoder):
    r"""
    Encoder for Reed-Muller codes which encodes appropiate multivariate polynomials into codewords.

    INPUT:

    - ``code`` -- The associated code of this encoder.

    -``polynomial_ring`` -- The polynomial field from which the message is chosen.

    EXAMPLES::

        sage: C1=codes.ReedMullerCode(GF(2), 2, 4)
        sage: E1=codes.encoders.ReedMullerPolynomialEncoder(C1)
        sage: E1
        Evaluation polynomial-style encoder for Binary Reed Muller Code of order 2 and number of variables 4
        sage: C2=codes.ReedMullerCode(GF(3), 2, 2)
        sage: E2=codes.encoders.ReedMullerPolynomialEncoder(C2)
        sage: E2
        Evaluation polynomial-style encoder for 3-ary Reed Muller Code of order 2 and number of variables 2

    We can also pass a predefined polynomial ring::

        sage: R=PolynomialRing(GF(3), 2, 'y')
        sage: C=codes.ReedMullerCode(GF(3), 2, 2)
        sage: E=codes.encoders.ReedMullerPolynomialEncoder(C, R)
        sage: E
        Evaluation polynomial-style encoder for 3-ary Reed Muller Code of order 2 and number of variables 2

    Actually, we can construct the encoder from ``C`` directly::

        sage: E = C1.encoder("EvaluationPolynomial")
        sage: E
        Evaluation polynomial-style encoder for Binary Reed Muller Code of order 2 and number of variables 4
    """

    def __init__(self, code, polynomial_ring='default'):
        r"""
        TESTS:

        If ``code`` is not a GRS code, an error is raised::

            sage: C  = codes.RandomLinearCode(10, 4, GF(11))
            sage: codes.encoders.ReedMullerPolynomialEncoder(C)
            Traceback (most recent call last):
            ...
            ValueError: the code has to be a Reed Muller code

        If the polynomial ring passed is not according to the requirement (over a different field or different number of variables) then an error is raised::

            sage: F=GF(59)
            sage: R.<x,y,z,w>=F[]
            sage: C=codes.ReedMullerCode(F, 2, 3)
            sage: E=codes.encoders.ReedMullerPolynomialEncoder(C, R)
            Traceback (most recent call last):
            ...
            ValueError: The Polynomial ring should be on Finite Field of size 59 and should have 3 variables
        """
        if not (
            isinstance(code, QAryReedMullerCode)
                or isinstance(code, BinaryReedMullerCode)):
            raise ValueError("the code has to be a Reed Muller code")
        super(ReedMullerPolynomialEncoder, self).__init__(code)
        if (polynomial_ring == 'default'):
            self._polynomial_ring = PolynomialRing(
                code.base_field(), code.number_of_variables(), 'x')
        else:
            if (polynomial_ring.base_ring() == code.base_field()) and (
                    len(polynomial_ring.variable_names()) == code.number_of_variables()):
                self._polynomial_ring = polynomial_ring
            else:
                raise ValueError(
                    "The Polynomial ring should be on %s and should have %s variables" %
                    (code.base_field(), code.number_of_variables()))

    def _repr_(self):
        r"""
        Returns a string representation of ``self``.

        EXAMPLES::

            sage: F = GF(59)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: E=codes.encoders.ReedMullerPolynomialEncoder(C)
            sage: E
            Evaluation polynomial-style encoder for 59-ary Reed Muller Code of order 2 and number of variables 4
        """
        return "Evaluation polynomial-style encoder for %s" % self.code()

    def _latex_(self):
        r"""
        Returns a string representation of ``self``.

        EXAMPLES::

            sage: F = GF(59)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: E=codes.encoders.ReedMullerPolynomialEncoder(C)
            sage: latex(E)
            \textnormal{Evaluation polynomial-style encoder for }59\textnormal{-ary Reed Muller Code of order} 2 \textnormal{and number of variables} 4
        """
        return "\\textnormal{Evaluation polynomial-style encoder for }%s" % self.code()._latex_()

    def __eq__(self, other):
        r"""
        Tests equality between ReedMullerVectorEncoder objects.

        EXAMPLES::

            sage: F = GF(11)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: D1 = codes.encoders.ReedMullerPolynomialEncoder(C)
            sage: D2 = codes.encoders.ReedMullerPolynomialEncoder(C)
            sage: D1.__eq__(D2)
            True
            sage: D1 is D2
            False
        """
        return (isinstance(other, ReedMullerPolynomialEncoder)
                ) and self.code() == other.code()

    def encode(self, p):
        r"""
        Transforms the polynomial ``p`` into a codeword of :meth:`code`.

        INPUT:

        - ``p`` -- A polynomial from the message space of ``self`` of degree
          less than ``self.code().order()``.

        OUTPUT:

        - A codeword in associated code of ``self``

        EXAMPLES::

            sage: F = GF(3)
            sage: Fx.<x0,x1> = F[]
            sage: C = codes.ReedMullerCode(F, 2, 2)
            sage: E = C.encoder("EvaluationPolynomial")
            sage: p = 1+x0+x1+x1^2+x1*x0
            sage: c = E.encode(p); c
            (1, 2, 0, 0, 2, 1, 1, 1, 1)
            sage: c in C
            True

        If a polynomial of too high degree is given, an error is raised::

            sage: p = x1^10
            sage: E.encode(p)
            Traceback (most recent call last):
            ...
            ValueError: The polynomial to encode must have degree at most 2

        If ``p`` is not an element of the proper polynomial ring, an error is raised::

            sage: Qy.<y1,y2> = QQ[]
            sage: p = y1^2 + 1
            sage: E.encode(p)
            Traceback (most recent call last):
            ...
            ValueError: The value to encode must be in Multivariate Polynomial Ring in x0, x1 over Finite Field of size 3
        """
        M = self.message_space()
        if p not in M:
            raise ValueError("The value to encode must be in %s" % M)
        C = self.code()
        if p.degree() > C.order():
            raise ValueError(
                "The polynomial to encode must have degree at most %s" %
                C.order())
        base_fieldTuple = Tuples(
            C.base_field().list(),
            C.number_of_variables())
        return vector(C.base_ring(), [p(x) for x in base_fieldTuple])

    def unencode_nocheck(self, c):
        r"""
        Returns the message corresponding to the codeword ``c``.

        Use this method with caution: it does not check if ``c``
        belongs to the code, and if this is not the case, the output is
        unspecified. Instead, use :meth:`unencode`.

        INPUT:

        - ``c`` -- A codeword of :meth:`code`.

        OUTPUT:

        - An polynomial of degree less than ``self.code().order()``.

        EXAMPLES::

            sage: F = GF(3)
            sage: C = codes.ReedMullerCode(F, 2, 2)
            sage: E = C.encoder("EvaluationPolynomial")
            sage: c = vector(F, (1, 2, 0, 0, 2, 1, 1, 1, 1))
            sage: c in C
            True
            sage: p = E.unencode_nocheck(c); p
            x0*x1 + x1^2 + x0 + x1 + 1
            sage: E.encode(p) == c
            True

        Note that no error is thrown if ``c`` is not a codeword, and that the
        result is undefined::

            sage: c = vector(F, (1, 2, 0, 0, 2, 1, 0, 1, 1))
            sage: c in C
            False
            sage: p = E.unencode_nocheck(c); p
            -x0*x1 - x1^2 + x0 + 1
            sage: E.encode(p) == c
            False

        """
        return _multivariate_polynomial_interpolation(
            c,
            self.code().number_of_variables(),
            self.code().order(),
            self.polynomial_ring())

    def message_space(self):
        r"""
        Returns the message space of ``self``

        EXAMPLES::

            sage: F = GF(11)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: E = C.encoder("EvaluationPolynomial")
            sage: E.message_space()
            Multivariate Polynomial Ring in x0, x1, x2, x3 over Finite Field of size 11
        """
        return self._polynomial_ring

    def polynomial_ring(self):
        r"""
        Returns the polynomial ring associated with ``self``

        EXAMPLES::

            sage: F = GF(11)
            sage: C = codes.ReedMullerCode(F, 2, 4)
            sage: E = C.encoder("EvaluationPolynomial")
            sage: E.polynomial_ring()
            Multivariate Polynomial Ring in x0, x1, x2, x3 over Finite Field of size 11
        """
        return self._polynomial_ring

QAryReedMullerCode._registered_encoders[
    "EvaluationVector"] = ReedMullerVectorEncoder
QAryReedMullerCode._registered_encoders[
    "EvaluationPolynomial"] = ReedMullerPolynomialEncoder

QAryReedMullerCode._registered_decoders["Syndrome"] = LinearCodeSyndromeDecoder

BinaryReedMullerCode._registered_encoders[
    "EvaluationVector"] = ReedMullerVectorEncoder
BinaryReedMullerCode._registered_encoders[
    "EvaluationPolynomial"] = ReedMullerPolynomialEncoder

BinaryReedMullerCode._registered_decoders[
    "Syndrome"] = LinearCodeSyndromeDecoder
