import streamlit as st
import pandas as pd
import geopy.distance
import requests

st.set_page_config(layout="wide")

# READ DATA
usable = True

processed_cpf_rncp = pd.read_csv(
    "data/processed_cpf_rncp.csv",
    dtype={"code_postal": "str", "code_departement": "str", "code_rncp": "int"},
)
processed_cpf_rncp.frais_ttc_tot_mean = processed_cpf_rncp.frais_ttc_tot_mean.astype(
    int
)

# BUILD INTERFACE
st.title("Recherche formations CPF")

remote = st.radio(
    label="À distance ?", options=["Oui", "Non"], horizontal=True, index=1
)

if remote == "Non":
    postal_code = st.text_input(
        label="Code postal", placeholder="44000", max_chars=5, key="postal_code"
    )

    available_rncp_codes = (
        processed_cpf_rncp[processed_cpf_rncp.code_departement == postal_code[:2]]
        .drop_duplicates(subset=["code_rncp"])
        .apply(lambda row: f"{row.code_rncp} | {row.intitule_formation}", axis=1)
    )

    rncp_code = st.selectbox(label="Code RNCP", options=available_rncp_codes)

    distance = st.radio(
        label="Rayon de recherche (km)",
        options=[5, 10, 50, 100],
        horizontal=True,
    )

else:
    available_rncp_codes = processed_cpf_rncp.apply(
        lambda row: f"{row.code_rncp} | {row.intitule_formation}", axis=1
    )
    rncp_code = st.selectbox(label="Code RNCP", options=available_rncp_codes)

rncp_code = int(rncp_code.split(" | ")[0]) if rncp_code else None

# SEARCH FOR RESULTS
if rncp_code:
    filtered_cpf = processed_cpf_rncp[processed_cpf_rncp.code_rncp == rncp_code]

    if usable:
        if remote == "Non":
            try:
                postal_code_longitude, postal_code_latitude = (
                    requests.get(
                        f"https://api-adresse.data.gouv.fr/search/?q={postal_code}"
                    )
                    .json()
                    .get("features")[0]
                    .get("geometry")
                    .get("coordinates")
                )

            except:
                st.error("Code postal non valide")
                usable = False

            filtered_cpf.loc[:, "distance"] = filtered_cpf.apply(
                lambda row: geopy.distance.geodesic(
                    (postal_code_latitude, postal_code_longitude),
                    (row["latitude"], row["longitude"]),
                ).meters,
                axis=1,
            )

            found_formations = filtered_cpf[
                (filtered_cpf.on_site)
                & (
                    (
                        (filtered_cpf.distance <= distance * 1000)
                        & (~filtered_cpf.secondary_establishment)
                    )
                    | (
                        (filtered_cpf.secondary_establishment)
                        & (filtered_cpf.code_postal == postal_code[:2])
                    )
                )
            ]

            found_formations.sort_values(
                by=["distance", "secondary_establishment"], ascending=True, inplace=True
            )

        else:
            found_formations = filtered_cpf[~filtered_cpf.on_site]

        filtered_found_formations = found_formations[
            [
                "nom_of",
                "intitule_formation",
                "nombre_heures_total_mean",
                "frais_ttc_tot_mean",
                "nom_commune_complet",
                "on_site",
            ]
        ]
        filtered_found_formations.columns = [
            "Organisme",
            "Nom formation",
            "Durée (h)",
            "Prix (€)",
            "Ville",
            "Présentiel",
        ]

        if not filtered_found_formations.empty:
            st.dataframe(filtered_found_formations)

        else:
            st.warning(
                "Aucune formation CPF correspondant à vos critères n'a été trouvée."
            )
