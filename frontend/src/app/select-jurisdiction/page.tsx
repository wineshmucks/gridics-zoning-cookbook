import { JurisdictionPickerPage } from '../../components/JurisdictionPickerPage'

type PageProps = {
  searchParams?: Promise<{
    returnTo?: string | string[]
  }>
}

export default function SelectJurisdictionPage({ searchParams }: PageProps) {
  return <JurisdictionPickerPage searchParams={searchParams} />
}
