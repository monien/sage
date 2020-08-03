r"""
Free submodules of tensor products of free modules
"""

#******************************************************************************
#       Copyright (C) 2020 Matthias Koeppe
#
#  Distributed under the terms of the GNU General Public License (GPL)
#  as published by the Free Software Foundation; either version 2 of
#  the License, or (at your option) any later version.
#                  http://www.gnu.org/licenses/
#******************************************************************************

from sage.misc.cachefunc import cached_method
from sage.sets.disjoint_set import DisjointSet
from .tensor_free_module import TensorFreeModule
from .finite_rank_free_module import FiniteRankFreeModule

class TensorFreeSubmodule_comp(TensorFreeModule):
    r"""
    Class for free submodules of tensor products of free modules
    that are defined by the symmetries of a
    :class:`~sage.tensor.modules.comp.Components` object.

    EXAMPLES::

        sage: from sage.tensor.modules.tensor_free_submodule import TensorFreeSubmodule_comp
        sage: M = FiniteRankFreeModule(ZZ, 3, name='M')
        sage: Sym2M = TensorFreeSubmodule_comp(M, (2, 0), sym=range(2)); Sym2M
        Free module of type-(2,0) tensors
        with Fully symmetric 2-indices components w.r.t. [0, 1, 2]
        on the Rank-3 free module M over the Integer Ring
    """
    def __init__(self, fmodule, tensor_type, name=None, latex_name=None,
                 sym=None, antisym=None):
        self._fmodule = fmodule
        self._tensor_type = tuple(tensor_type)
        # Create a tensor only because we need a Components object
        tensor = fmodule.tensor(tensor_type,
                                name=name, latex_name=latex_name,
                                sym=sym, antisym=antisym)
        frame = list(fmodule.irange())
        self._comp = tensor._new_comp(frame)
        rank = len(list(self._comp.non_redundant_index_generator()))
        # Skip TensorFreeModule.__init__
        FiniteRankFreeModule.__init__(self, fmodule._ring, rank, name=name,
                                      latex_name=latex_name,
                                      start_index=fmodule._sindex,
                                    output_formatter=fmodule._output_formatter)

    def _repr_(self):
        r"""
        Return a string representation of ``self``.

        EXAMPLES::

            sage: M = FiniteRankFreeModule(QQ, 2, name='M')
            sage: Sym2M = TensorFreeSubmodule_comp(M, (2, 0), sym=range(2)); Sym2M
            Free module of type-(2,0) tensors
            with Fully symmetric 2-indices components w.r.t. [0, 1, 2]
            on the Rank-3 free module M over the Integer Ring

        """
        return "Free module of type-({},{}) tensors with {} on the {}".format(
            self._tensor_type[0], self._tensor_type[1], self._comp, self._fmodule)

    def ambient_module(self):
        """
        Return the ambient module associated to this module.

        EXAMPLES::

            sage: from sage.tensor.modules.tensor_free_submodule import TensorFreeSubmodule_comp
            sage: M = FiniteRankFreeModule(ZZ, 3, name='M')
            sage: Sym0123x45M = TensorFreeSubmodule_comp(M, (6, 0), sym=((0, 1, 2, 3), (4, 5)))
            sage: T60M = M.tensor_module(6, 0)
            sage: Sym0123x45M.ambient_module() is T60M
            True
        """
        return self.base_module().tensor_module(*self.tensor_type())

    def is_submodule(self, other):
        r"""
        Return ``True`` if ``self`` is a submodule of ``other``.

        EXAMPLES::

            sage: from sage.tensor.modules.tensor_free_submodule import TensorFreeSubmodule_comp
            sage: M = FiniteRankFreeModule(ZZ, 3, name='M')
            sage: T60M = M.tensor_module(6, 0)
            sage: Sym0123x45M = TensorFreeSubmodule_comp(M, (6, 0), sym=((0, 1, 2, 3), (4, 5)))
            sage: Sym012x345M = TensorFreeSubmodule_comp(M, (6, 0), sym=((0, 1, 2), (3, 4, 5)))
            sage: Sym012345M  = TensorFreeSubmodule_comp(M, (6, 0), sym=((0, 1, 2, 3, 4, 5)))
            sage: Sym012345M.is_submodule(Sym012345M)
            True
            sage: Sym012345M.is_submodule(Sym0123x45M)
            True
            sage: Sym0123x45M.is_submodule(Sym012345M)
            False
            sage: Sym012x345M.is_submodule(Sym0123x45M)
            False
            sage: all(S.is_submodule(T60M) for S in (Sym0123x45M, Sym012x345M, Sym012345M))
            True

        """
        if self == other:
            return True
        self_base_module = self.base_module()
        self_tensor_type = self.tensor_type()
        try:
            other_base_module = other.base_module()
            other_tensor_type = other.tensor_type()
        except AttributeError:
            return False
        if self_base_module != other_base_module:
            return False
        if self_tensor_type != other_tensor_type:
            return False
        # Use the union-find data structure
        def is_coarsening_of(self_sym_list, other_sym_list):
            S = DisjointSet(self_tensor_type[0] + self_tensor_type[1])
            for index_set in self_sym_list:
                i = index_set[0]
                for j in index_set[1:]:
                    S.union(i, j)
            for index_set in other_sym_list:
                i = S.find(index_set[0])
                for j in index_set[1:]:
                    if S.find(j) != i:
                        return False
            return True
        # Similar code is in Component.contract, should refactor.
        try:
            other_sym = other._comp._sym
            other_antisym = other._comp._antisym
        except AttributeError:
            # other is full tensor module (no symmetry)
            return True
        if not is_coarsening_of(self._comp._sym, other_sym):
            return False
        if not is_coarsening_of(self._comp._antisym, other._comp._antisym):
            return False
        return True
