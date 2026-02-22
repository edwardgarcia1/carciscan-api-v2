from rdkit import Chem
from rdkit.Chem import Descriptors
from typing import Optional, Dict
from rdkit.Chem import SaltRemover

def calculate_rdkit_descriptors(smiles: str) -> Optional[Dict[str, float]]:
    """
    Calculates all available RDKit descriptors for a given SMILES string.
    Returns a dictionary of {descriptor_name: value}.
    """
    if not smiles:
        return None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    remover = SaltRemover.SaltRemover()
    mol = remover.StripMol(mol, dontRemoveEverything=True)
    if mol.GetNumAtoms() == 0:
        mol = Chem.MolFromSmiles(smiles)

    canonical_smiles = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    mol_canon = Chem.MolFromSmiles(canonical_smiles)
    if mol_canon is None:
        return None

    # CalcMolDescriptors returns a dictionary of {descriptor_name: value}
    descriptor_dict: Dict[str, float] = Descriptors.CalcMolDescriptors(mol)

    return descriptor_dict